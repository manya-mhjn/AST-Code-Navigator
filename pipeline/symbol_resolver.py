# pipeline/symbol_resolver.py

class SymbolResolver:
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.alias_map = {}       # file_path -> {local_name -> target_id}
        self.global_vars = set()  # set of all Variable node IDs
        self.functions = set()    # set of all Function node IDs
        self.classes = set()      # set of all Class node IDs
        self.attributes = set()   # set of all InstanceAttribute node IDs
        self.inheritance_map = {} # class_id -> list of parent class_ids (for MRO)
        
    def resolve_and_ingest(self):
        print("Starting post-ingestion Symbol Resolution...")
        with self.driver.session() as session:
            self._build_registries(session)
            self._build_alias_maps(session)
            self._build_inheritance_map(session)
            
            self._resolve_calls_and_instantiations(session)
            self._resolve_inherits(session)
            self._resolve_uses_variable(session)
            self._resolve_uses_instance_attribute(session)
            
        print("Symbol Resolution complete!")

    def _build_registries(self, session):
        """Fetch all known node IDs for quick validation."""
        for record in session.run("MATCH (v:Variable) RETURN v.id AS id"):
            self.global_vars.add(record["id"])
        for record in session.run("MATCH (f:Function) RETURN f.id AS id"):
            self.functions.add(record["id"])
        for record in session.run("MATCH (c:Class) RETURN c.id AS id"):
            self.classes.add(record["id"])
        for record in session.run("MATCH (a:InstanceAttribute) RETURN a.id AS id"):
            self.attributes.add(record["id"])

    def _build_alias_maps(self, session):
        """Map internal imports using coalesce for robust naming."""
        result = session.run("""
            MATCH (f:File)-[:IMPORTS]->(i:Import)
            RETURN f.id AS file_id, 
                   coalesce(i.alias, i.imported_symbol, i.module) AS local_name, 
                   i.module AS module, 
                   i.imported_symbol AS symbol
        """)
        for record in result:
            file_id = record["file_id"]
            if file_id not in self.alias_map:
                self.alias_map[file_id] = {}
            
            mod_path = record["module"].replace('.', '/') + ".py"
            # Distinguish between 'from utils import helper' and 'import utils'
            if record["symbol"]:
                target_id = f"{mod_path}::{record['symbol']}"
            else:
                target_id = mod_path
                
            self.alias_map[file_id][record['local_name']] = target_id

    def _build_inheritance_map(self, session):
        """Build an in-memory map of Class inheritance for fast traversal."""
        # Using the raw INHERITS_FROM edge because RESOLVED_INHERITS happens later
        result = session.run("""
            MATCH (c:Class)-[:INHERITS_FROM]->(base:Class) 
            RETURN c.id AS child_id, base.id AS parent_id
        """)
        for record in result:
            child = record["child_id"]
            parent = record["parent_id"]
            if child not in self.inheritance_map:
                self.inheritance_map[child] = []
            self.inheritance_map[child].append(parent)

    def _resolve_target(self, caller_id, target_name):
        """Attempts to find the fully qualified Node ID for a string target."""
        file_id = caller_id.split("::")[0]
        
        # 1. Is it a class method? (e.g. self.validate)
        if target_name.startswith("self."):
            if "::" in caller_id and "." in caller_id:
                class_id = caller_id.rsplit(".", 1)[0]
                method_name = target_name.split(".")[1]
                return f"{class_id}.{method_name}"
            return None

        # 2. Is it imported?
        if file_id in self.alias_map and target_name in self.alias_map[file_id]:
            return self.alias_map[file_id][target_name]
            
        # 3. Is it in the same file?
        return f"{file_id}::{target_name}"

    def _resolve_calls_and_instantiations(self, session):
        result = session.run("MATCH (src)-[r:CALLS]->(t:Target) RETURN src.id AS src_id, t.name AS target_name")
        resolved_calls = []
        instantiations = []
        
        for record in result:
            src_id = record["src_id"]
            target_id = self._resolve_target(src_id, record["target_name"])
            
            if target_id in self.functions:
                resolved_calls.append({"src": src_id, "target": target_id})
            elif target_id in self.classes:
                instantiations.append({"src": src_id, "target": target_id})
                
        if resolved_calls:
            session.run("""
                UNWIND $batch AS row
                MATCH (src {id: row.src}), (tgt:Function {id: row.target})
                MERGE (src)-[:RESOLVED_CALLS]->(tgt)
            """, batch=resolved_calls)
            
        if instantiations:
            session.run("""
                UNWIND $batch AS row
                MATCH (src {id: row.src}), (tgt:Class {id: row.target})
                MERGE (src)-[:INSTANTIATES]->(tgt)
            """, batch=instantiations)

    def _resolve_inherits(self, session):
        result = session.run("MATCH (c:Class)-[r:INHERITS_FROM]->(base:Class) RETURN c.id AS src_id, base.name AS target_name")
        resolved = []
        for record in result:
            target_id = self._resolve_target(record["src_id"], record["target_name"])
            if target_id in self.classes:
                resolved.append({"src": record["src_id"], "target": target_id})
                
        if resolved:
            session.run("""
                UNWIND $batch AS row
                MATCH (src:Class {id: row.src}), (tgt:Class {id: row.target})
                MERGE (src)-[:RESOLVED_INHERITS]->(tgt)
            """, batch=resolved)

    def _resolve_uses_variable(self, session):
        result = session.run("MATCH (src)-[r:USES_VARIABLE]->(t:RawVariable) RETURN src.id AS src_id, t.name AS target_name")
        resolved = []
        for record in result:
            target_id = self._resolve_target(record["src_id"], record["target_name"])
            if target_id in self.global_vars:
                resolved.append({"src": record["src_id"], "target": target_id})
                
        if resolved:
            session.run("""
                UNWIND $batch AS row
                MATCH (src {id: row.src}), (tgt:Variable {id: row.target})
                MERGE (src)-[:RESOLVED_USES_VARIABLE]->(tgt)
            """, batch=resolved)

    def _find_attribute_in_hierarchy(self, class_id, attr_name):
        """Recursively search for an attribute in the class and its parents."""
        attr_id = f"{class_id}::inst_attr::{attr_name}"
        if attr_id in self.attributes:
            return attr_id
            
        # Fallback: check parents (Inheritance Traversal)
        if class_id in self.inheritance_map:
            for parent_id in self.inheritance_map[class_id]:
                found_id = self._find_attribute_in_hierarchy(parent_id, attr_name)
                if found_id:
                    return found_id
        return None

    def _resolve_uses_instance_attribute(self, session):
        result = session.run("MATCH (src)-[r:USES_INSTANCE_ATTRIBUTE]->(t:RawInstanceAttribute) RETURN src.id AS src_id, t.name AS target_name")
        resolved = []
        for record in result:
            src_id = record["src_id"]
            if "::" in src_id and "." in src_id:
                class_id = src_id.rsplit(".", 1)[0]
                # Initiate the hierarchy search instead of blindly assuming it belongs to the child
                target_attr_id = self._find_attribute_in_hierarchy(class_id, record["target_name"])
                
                if target_attr_id:
                    resolved.append({"src": src_id, "target": target_attr_id})
                
        if resolved:
            session.run("""
                UNWIND $batch AS row
                MATCH (src {id: row.src}), (tgt:InstanceAttribute {id: row.target})
                MERGE (src)-[:RESOLVED_USES_INST_ATTR]->(tgt)
            """, batch=resolved)
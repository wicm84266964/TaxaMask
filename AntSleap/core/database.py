import sqlite3
import os

class MultiModalDB:
    """
    Real SQLite backend to manage Taxonomic Descriptions.
    Connects to 'taxonomy.db'.
    """
    def __init__(self, db_path=None):
        if db_path is None:
            # Default to 'taxonomy.db' in the parent directory of this file (core/../taxonomy.db)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "taxonomy.db")
        else:
            self.db_path = db_path
            
        self._init_db()

    def _init_db(self):
        """Initialize database with schema and some sample data if empty."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Table: Taxonomy Descriptions
        c.execute('''CREATE TABLE IF NOT EXISTS descriptions (
                        id INTEGER PRIMARY KEY,
                        genus TEXT,
                        body_part TEXT,
                        description TEXT
                    )''')
        
        # Check if empty, if so, seed with sample data (Simulating your existing PDF extraction)
        c.execute('SELECT count(*) FROM descriptions')
        if c.fetchone()[0] == 0:
            print("Seeding database with sample taxonomy data...")
            samples = [
                ('Camponotus', 'Head', 'Head usually massive, often wider than the thorax. Mandibles powerful and triangular.'),
                ('Camponotus', 'Mesosoma', 'Mesosoma typically arcuate (arched) in profile. Propodeum often compressed.'),
                ('Camponotus', 'Gaster', 'First gastral segment covers less than half the length of the gaster.'),
                ('Polyrhachis', 'Head', 'Head often with distinct ridges or spines near the eyes.'),
                ('Polyrhachis', 'Mesosoma', 'Mesosoma armed with spines on pronotum and propodeum. Petiole usually scale-like with spines.'),
                ('Polyrhachis', 'Gaster', 'Gaster globally rounded, first segment covering a large portion.')
            ]
            c.executemany('INSERT INTO descriptions (genus, body_part, description) VALUES (?, ?, ?)', samples)
            conn.commit()
            
        conn.close()

    def query_trait_description(self, genus, body_part):
        """
        Retrieves the standard taxonomic text description.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT description FROM descriptions WHERE genus=? AND body_part=?', (genus, body_part))
        result = c.fetchone()
        conn.close()
        
        if result:
            return result[0]
        else:
            return f"No description found for {genus} - {body_part}."

    def add_custom_description(self, genus, body_part, text):
        """Allows adding new knowledge to the DB."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO descriptions (genus, body_part, description) VALUES (?, ?, ?)', (genus, body_part, text))
        conn.commit()
        conn.close()
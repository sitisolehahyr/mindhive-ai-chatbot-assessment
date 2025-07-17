import sqlite3
import json
import re
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime
from app.config import ZUS_OUTLETS_FILE, DEFAULT_DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SQLQuery:
    """Structured SQL query with metadata"""
    sql: str
    parameters: List[Any]
    confidence: float
    explanation: str
    query_type: str  # SELECT, INSERT, UPDATE, DELETE


@dataclass
class QueryResult:
    """SQL query execution result"""
    success: bool
    data: List[Dict[str, Any]]
    columns: List[str]
    row_count: int
    execution_time: float
    error_message: Optional[str] = None


class ZUSOutletText2SQL:
    """
    Text-to-SQL system for ZUS Coffee outlets
    
    Features:
    - Natural language to SQL translation
    - Safe SQL execution with parameter binding
    - Comprehensive outlet database schema
    - Query validation and sanitization
    - Error handling and fallbacks
    """
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.connection = None
        
        # SQL templates for common queries
        self.query_templates = {
            "location_search": {
                "patterns": [
                    r"outlets? in (.+)",
                    r"(?:find|search|locate).*outlets?.*(?:in|at|near) (.+)",
                    r"(.+) outlets?",
                    r"where.*outlets?.*(.+)"
                ],
                "sql": "SELECT * FROM outlets WHERE LOWER(city) LIKE LOWER(?) OR LOWER(state) LIKE LOWER(?) OR LOWER(address) LIKE LOWER(?)",
                "confidence": 0.9
            },
            "opening_hours": {
                "patterns": [
                    r"(?:opening|operating) hours?.*(.+)",
                    r"what time.*(?:open|close).*(.+)",
                    r"hours?.*(.+)",
                    r"when.*open.*(.+)"
                ],
                "sql": "SELECT name, operating_hours FROM outlets WHERE LOWER(name) LIKE LOWER(?) OR LOWER(city) LIKE LOWER(?)",
                "confidence": 0.85
            },
            "services": {
                "patterns": [
                    r"services.*(.+)",
                    r"what.*available.*(.+)",
                    r"facilities.*(.+)",
                    r"(?:wifi|parking|dine).*(.+)"
                ],
                "sql": "SELECT name, services, features FROM outlets WHERE LOWER(name) LIKE LOWER(?) OR LOWER(city) LIKE LOWER(?)",
                "confidence": 0.8
            },
            "contact_info": {
                "patterns": [
                    r"(?:phone|contact|number).*(.+)",
                    r"how.*contact.*(.+)",
                    r"call.*(.+)"
                ],
                "sql": "SELECT name, phone, email, address FROM outlets WHERE LOWER(name) LIKE LOWER(?) OR LOWER(city) LIKE LOWER(?)",
                "confidence": 0.85
            },
            "all_outlets": {
                "patterns": [
                    r"(?:all|list).*outlets?",
                    r"show.*outlets?",
                    r"outlets?.*list"
                ],
                "sql": "SELECT name, city, state, outlet_type FROM outlets ORDER BY city, name",
                "confidence": 0.95
            },
            "outlet_count": {
                "patterns": [
                    r"how many outlets?",
                    r"number of outlets?",
                    r"count.*outlets?"
                ],
                "sql": "SELECT COUNT(*) as total_outlets, COUNT(DISTINCT city) as cities, COUNT(DISTINCT state) as states FROM outlets",
                "confidence": 0.9
            }
        }
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with outlets schema"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            
            # Create outlets table
            self._create_schema()
            
            # Load data if table is empty
            cursor = self.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM outlets")
            count = cursor.fetchone()[0]
            
            if count == 0:
                self._load_initial_data()
            
            logger.info(f"Database initialized with {count} outlets")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def _create_schema(self):
        """Create database schema for outlets"""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS outlets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            postcode TEXT,
            phone TEXT,
            email TEXT,
            operating_hours TEXT,  -- JSON string
            services TEXT,         -- JSON string  
            coordinates TEXT,      -- JSON string
            outlet_type TEXT,
            features TEXT,         -- JSON string
            capacity INTEGER,
            established DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_outlets_city ON outlets(city);
        CREATE INDEX IF NOT EXISTS idx_outlets_state ON outlets(state);
        CREATE INDEX IF NOT EXISTS idx_outlets_type ON outlets(outlet_type);
        CREATE INDEX IF NOT EXISTS idx_outlets_name ON outlets(name);
        """
        
        self.connection.executescript(schema_sql)
        self.connection.commit()
    
    def _load_initial_data(self):
        """Load initial outlet data from JSON file"""
        json_path = str(ZUS_OUTLETS_FILE)
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                outlets_data = json.load(f)
            
            cursor = self.connection.cursor()
            
            for outlet in outlets_data:
                # Convert JSON fields to strings
                operating_hours = json.dumps(outlet.get('operating_hours', {}))
                services = json.dumps(outlet.get('services', []))
                coordinates = json.dumps(outlet.get('coordinates', {}))
                features = json.dumps(outlet.get('features', []))
                
                cursor.execute("""
                    INSERT INTO outlets (
                        name, address, city, state, postcode, phone, email,
                        operating_hours, services, coordinates, outlet_type,
                        features, capacity, established
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    outlet.get('name'),
                    outlet.get('address'),
                    outlet.get('city'),
                    outlet.get('state'),
                    outlet.get('postcode'),
                    outlet.get('phone'),
                    outlet.get('email'),
                    operating_hours,
                    services,
                    coordinates,
                    outlet.get('outlet_type'),
                    features,
                    outlet.get('capacity'),
                    outlet.get('established')
                ))
            
            self.connection.commit()
            logger.info(f"Loaded {len(outlets_data)} outlets into database")
            
        except Exception as e:
            logger.error(f"Failed to load initial data: {e}")
            raise
    
    def parse_natural_language_query(self, query: str) -> Optional[SQLQuery]:
        """
        Parse natural language query and convert to SQL
        
        Args:
            query: Natural language query about outlets
            
        Returns:
            SQLQuery object or None if parsing fails
        """
        query_lower = query.lower().strip()
        
        # Try to match query against templates
        for query_type, template in self.query_templates.items():
            for pattern in template["patterns"]:
                match = re.search(pattern, query_lower)
                if match:
                    return self._build_sql_from_template(
                        query_type, template, match, query
                    )
        
        # Fallback: try to extract location/name from query
        return self._build_fallback_query(query)
    
    def _build_sql_from_template(self, query_type: str, template: Dict[str, Any], 
                                match: re.Match, original_query: str) -> SQLQuery:
        """Build SQL query from matched template"""
        sql = template["sql"]
        confidence = template["confidence"]
        parameters = []
        
        if query_type == "all_outlets" or query_type == "outlet_count":
            # No parameters needed
            parameters = []
        else:
            # Extract location/name from match
            if match.groups():
                location = match.group(1).strip()
                # For most queries, we search in name, city, and sometimes address
                if query_type == "location_search":
                    parameters = [f"%{location}%", f"%{location}%", f"%{location}%"]
                else:
                    parameters = [f"%{location}%", f"%{location}%"]
            else:
                # Generic search
                parameters = ["%", "%"]
        
        explanation = f"Searching for {query_type.replace('_', ' ')} based on: '{original_query}'"
        
        return SQLQuery(
            sql=sql,
            parameters=parameters,
            confidence=confidence,
            explanation=explanation,
            query_type="SELECT"
        )
    
    def _build_fallback_query(self, query: str) -> Optional[SQLQuery]:
        """Build fallback query for unmatched patterns"""
        # Extract potential location names
        common_locations = [
            'kuala lumpur', 'kl', 'petaling jaya', 'pj', 'selangor',
            'bangsar', 'mid valley', 'klcc', '1 utama', 'sunway',
            'putrajaya', 'ioi', 'gardens'
        ]
        
        query_lower = query.lower()
        found_location = None
        
        for location in common_locations:
            if location in query_lower:
                found_location = location
                break
        
        if found_location:
            sql = "SELECT * FROM outlets WHERE LOWER(city) LIKE LOWER(?) OR LOWER(address) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?)"
            parameters = [f"%{found_location}%", f"%{found_location}%", f"%{found_location}%"]
            explanation = f"General search for outlets related to '{found_location}'"
            confidence = 0.6
        else:
            # Very generic search
            sql = "SELECT name, city, state, phone FROM outlets ORDER BY city, name LIMIT 10"
            parameters = []
            explanation = "Showing general outlet information"
            confidence = 0.4
        
        return SQLQuery(
            sql=sql,
            parameters=parameters,
            confidence=confidence,
            explanation=explanation,
            query_type="SELECT"
        )
    
    def execute_query(self, sql_query: SQLQuery) -> QueryResult:
        """
        Execute SQL query safely with parameter binding
        
        Args:
            sql_query: SQLQuery object to execute
            
        Returns:
            QueryResult with execution results
        """
        start_time = datetime.now()
        
        try:
            # Validate SQL query (basic safety checks)
            if not self._is_safe_query(sql_query.sql):
                return QueryResult(
                    success=False,
                    data=[],
                    columns=[],
                    row_count=0,
                    execution_time=0.0,
                    error_message="Query failed safety validation"
                )
            
            cursor = self.connection.cursor()
            cursor.execute(sql_query.sql, sql_query.parameters)
            
            # Fetch results
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            
            # Convert rows to dictionaries
            data = []
            for row in rows:
                row_dict = {}
                for i, column in enumerate(columns):
                    value = row[i]
                    # Parse JSON fields back to objects
                    if column in ['operating_hours', 'services', 'coordinates', 'features'] and value:
                        try:
                            value = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            pass  # Keep as string if parsing fails
                    row_dict[column] = value
                data.append(row_dict)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Query executed successfully: {len(data)} rows returned")
            
            return QueryResult(
                success=True,
                data=data,
                columns=columns,
                row_count=len(data),
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Query execution failed: {e}")
            
            return QueryResult(
                success=False,
                data=[],
                columns=[],
                row_count=0,
                execution_time=execution_time,
                error_message=str(e)
            )
    
    def _is_safe_query(self, sql: str) -> bool:
        """Basic SQL safety validation"""
        sql_lower = sql.lower().strip()
        
        # Only allow SELECT statements
        if not sql_lower.startswith('select'):
            return False
        
        # Disallow dangerous keywords
        dangerous_keywords = [
            'drop', 'delete', 'insert', 'update', 'alter', 'create',
            'exec', 'execute', 'sp_', 'xp_', '--', ';'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_lower:
                return False
        
        return True
    
    def query_outlets(self, natural_query: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Main interface for querying outlets with natural language
        
        Args:
            natural_query: Natural language query
            
        Returns:
            Tuple of (success, explanation, results)
        """
        try:
            # Parse natural language to SQL
            sql_query = self.parse_natural_language_query(natural_query)
            
            if not sql_query:
                return False, "Could not understand the query", []
            
            # Execute SQL query
            result = self.execute_query(sql_query)
            
            if not result.success:
                return False, f"Query execution failed: {result.error_message}", []
            
            explanation = f"{sql_query.explanation}. Found {result.row_count} result(s)."
            
            return True, explanation, result.data
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return False, f"Error processing query: {str(e)}", []
    
    def get_schema_info(self) -> Dict[str, Any]:
        """Get database schema information for query assistance"""
        try:
            cursor = self.connection.cursor()
            
            # Get table info
            cursor.execute("PRAGMA table_info(outlets)")
            columns = cursor.fetchall()
            
            # Get sample data
            cursor.execute("SELECT * FROM outlets LIMIT 3")
            sample_data = cursor.fetchall()
            
            # Get statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_outlets,
                    COUNT(DISTINCT city) as unique_cities,
                    COUNT(DISTINCT state) as unique_states,
                    COUNT(DISTINCT outlet_type) as outlet_types
                FROM outlets
            """)
            stats = cursor.fetchone()
            
            return {
                "columns": [{"name": col[1], "type": col[2]} for col in columns],
                "sample_data": [dict(row) for row in sample_data],
                "statistics": dict(stats)
            }
            
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            return {}
    
    def generate_response_summary(self, query: str, results: List[Dict[str, Any]], 
                                explanation: str) -> str:
        """
        Generate human-friendly summary of query results
        
        Args:
            query: Original natural language query
            results: Query results
            explanation: Query explanation
            
        Returns:
            Formatted summary string
        """
        if not results:
            return f"I couldn't find any ZUS Coffee outlets matching '{query}'. You might want to try searching for specific cities like 'Kuala Lumpur', 'Petaling Jaya', or 'Selangor'."
        
        summary_parts = []
        summary_parts.append(f"I found {len(results)} ZUS Coffee outlet(s) for '{query}':")
        
        for i, outlet in enumerate(results[:5], 1):  # Show top 5 results
            name = outlet.get('name', 'Unknown Outlet')
            city = outlet.get('city', '')
            state = outlet.get('state', '')
            
            location = f"{city}, {state}" if city and state else (city or state or '')
            
            summary_parts.append(f"\n{i}. **{name}**")
            if location:
                summary_parts.append(f"   📍 {location}")
            
            # Add specific info based on query type
            if any(word in query.lower() for word in ['hour', 'open', 'time']):
                hours = outlet.get('operating_hours', {})
                if isinstance(hours, dict) and hours:
                    if 'daily' in hours:
                        summary_parts.append(f"   🕒 Daily: {hours['daily']}")
                    elif 'monday' in hours:
                        summary_parts.append(f"   🕒 Mon-Fri: {hours.get('monday', 'Not available')}")
            
            if any(word in query.lower() for word in ['phone', 'contact', 'call']):
                phone = outlet.get('phone')
                if phone:
                    summary_parts.append(f"   📞 {phone}")
            
            if any(word in query.lower() for word in ['service', 'wifi', 'parking']):
                services = outlet.get('services', [])
                if isinstance(services, list) and services:
                    summary_parts.append(f"   🔧 Services: {', '.join(services[:3])}")
        
        if len(results) > 5:
            summary_parts.append(f"\n...and {len(results) - 5} more outlets.")
        
        return "\n".join(summary_parts)
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()


if __name__ == "__main__":
    # Example usage
    text2sql = ZUSOutletText2SQL()
    
    # Test queries
    test_queries = [
        "outlets in Kuala Lumpur",
        "opening hours for SS2",
        "phone number for Mid Valley outlet",
        "all outlets",
        "how many outlets are there?",
        "outlets with WiFi",
        "ZUS Coffee in Selangor"
    ]
    
    for query in test_queries:
        print(f"\n--- Query: '{query}' ---")
        
        success, explanation, results = text2sql.query_outlets(query)
        
        if success:
            print(f"✅ {explanation}")
            
            # Generate summary
            summary = text2sql.generate_response_summary(query, results, explanation)
            print(f"\nSummary:\n{summary}")
            
            # Show raw results (first 2)
            print(f"\nRaw Results (showing first 2):")
            for i, result in enumerate(results[:2], 1):
                print(f"{i}. {json.dumps(result, indent=2, default=str)}")
        else:
            print(f"❌ {explanation}")
    
    # Show schema info
    print(f"\n--- Database Schema ---")
    schema = text2sql.get_schema_info()
    print(json.dumps(schema, indent=2, default=str))
    
    text2sql.close()
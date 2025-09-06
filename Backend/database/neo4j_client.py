from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from config.settings import Settings
import logging

logger = logging.getLogger(__name__)

class Neo4jClient:
    """Neo4j database client for precedent graph queries"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.driver: Optional[AsyncDriver] = None
        
    async def connect(self):
        """Initialize Neo4j connection"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password)
            )
            await self.verify_connectivity()
            logger.info("Neo4j connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    async def verify_connectivity(self):
        """Verify database connectivity"""
        async with self.driver.session() as session:
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            assert record["test"] == 1
    
    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
    
    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        Execute a Cypher query
        
        Args:
            query: Cypher query string
            parameters: Query parameters
        """
        if not self.driver:
            await self.connect()
        
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            records = []
            async for record in result:
                records.append(dict(record))
            return records
    
    async def find_similar_deals(
        self,
        deal_characteristics: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict]:
        """Find similar deals based on characteristics"""
        query = """
        MATCH (d:Deal)-[:INVOLVES]->(e:Election)
        WHERE e.type = $election_type
        AND d.value >= $min_value AND d.value <= $max_value
        AND d.date >= $min_date
        OPTIONAL MATCH (d)-[:HAS_PARTY]->(p:Party)
        OPTIONAL MATCH (d)-[:HAS_ADVISOR]->(a:Advisor)
        RETURN d, e, collect(DISTINCT p) as parties, collect(DISTINCT a) as advisors
        ORDER BY d.date DESC
        LIMIT $limit
        """
        
        parameters = {
            'election_type': deal_characteristics.get('election_type', '338'),
            'min_value': deal_characteristics.get('min_value', 0),
            'max_value': deal_characteristics.get('max_value', 1e12),
            'min_date': deal_characteristics.get('min_date', '2020-01-01'),
            'limit': limit
        }
        
        return await self.execute_query(query, parameters)
    
    async def get_deal_network(self, deal_id: str) -> Dict:
        """Get the network of entities related to a deal"""
        query = """
        MATCH (d:Deal {id: $deal_id})
        OPTIONAL MATCH (d)-[r1:INVOLVES]->(e:Election)
        OPTIONAL MATCH (d)-[r2:HAS_PARTY]->(p:Party)
        OPTIONAL MATCH (d)-[r3:HAS_ADVISOR]->(a:Advisor)
        OPTIONAL MATCH (d)-[r4:REFERENCES]->(ref:Deal)
        RETURN d, 
               collect(DISTINCT e) as elections,
               collect(DISTINCT p) as parties,
               collect(DISTINCT a) as advisors,
               collect(DISTINCT ref) as references
        """
        
        result = await self.execute_query(query, {'deal_id': deal_id})
        return result[0] if result else {}
    
    async def create_deal(self, deal_data: Dict) -> str:
        """Create a new deal in the graph"""
        query = """
        CREATE (d:Deal {
            id: randomUUID(),
            title: $title,
            description: $description,
            value: $value,
            date: $date,
            created_at: datetime()
        })
        RETURN d.id as deal_id
        """
        
        result = await self.execute_query(query, deal_data)
        return result[0]['deal_id'] if result else None
    
    async def link_election_to_deal(
        self,
        deal_id: str,
        election_data: Dict
    ) -> bool:
        """Link an election to a deal"""
        query = """
        MATCH (d:Deal {id: $deal_id})
        CREATE (e:Election {
            type: $type,
            section: $section,
            filing_deadline: $filing_deadline
        })
        CREATE (d)-[:INVOLVES]->(e)
        RETURN e
        """
        
        parameters = {
            'deal_id': deal_id,
            **election_data
        }
        
        result = await self.execute_query(query, parameters)
        return len(result) > 0
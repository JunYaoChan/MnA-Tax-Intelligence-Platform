#!/usr/bin/env python3
"""
Database Population Script for Tax Intelligence Platform

This script helps populate your Supabase and Neo4j databases with sample data
for testing the Tax Intelligence Platform.

Usage:
    python populate_databases.py

Available functions:
- populate_supabase_sample(): Add sample tax documents to Supabase
- populate_neo4j_sample(): Add sample deal network to Neo4j
- test_connections(): Test both database connections
"""

import asyncio
import logging
from config.settings import Settings
from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_supabase_connection():
    """Test Supabase connection and display table info."""
    try:
        settings = Settings()
        store = SupabaseVectorStore(settings)

        logger.info("🧪 Testing Supabase connection...")

        # Try to query the database
        results = await store.search("test query", 5)
        logger.info(f"✅ Supabase connected. Search returned {len(results)} results.")

        return True
    except Exception as e:
        logger.error(f"❌ Supabase connection failed: {e}")
        return False

async def test_neo4j_connection():
    """Test Neo4j connection and display database info."""
    try:
        settings = Settings()
        client = Neo4jClient(settings)

        await client.connect()
        logger.info("✅ Neo4j connected successfully.")

        # Test query
        result = await client.execute_query("MATCH (n) RETURN count(n) as node_count")
        if result:
            node_count = result[0]['node_count']
            logger.info(f"📊 Neo4j database contains {node_count} nodes.")

        return True
    except Exception as e:
        logger.error(f"❌ Neo4j connection failed: {e}")
        return False
    finally:
        if client.driver:
            await client.close()

async def populate_supabase_sample():
    """Populate Supabase with sample tax documents."""
    try:
        settings = Settings()
        store = SupabaseVectorStore(settings)

        logger.info("📚 Populating Supabase with sample documents...")

        # Insert sample documents
        inserted = await store.insert_sample_documents()
        logger.info(f"✅ Successfully inserted {inserted} sample documents into Supabase.")

        # Test search
        results = await store.search("election requirements", 3)
        logger.info(f"🔍 Test search found {len(results)} documents.")

        for result in results:
            logger.info(f"   - {result.get('title', 'Unknown')}")

        return True
    except Exception as e:
        logger.error(f"❌ Failed to populate Supabase: {e}")
        return False

async def populate_neo4j_sample():
    """Populate Neo4j with sample deal network."""
    client = None
    try:
        settings = Settings()
        client = Neo4jClient(settings)

        await client.connect()
        logger.info("🌐 Populating Neo4j with sample deal network...")

        # Create constraints first
        constraints = [
            "CREATE CONSTRAINT deal_id_unique IF NOT EXISTS FOR (d:Deal) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT election_id_unique IF NOT EXISTS FOR (e:Election) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT party_name_unique IF NOT EXISTS FOR (p:Party) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT advisor_name_unique IF NOT EXISTS FOR (a:Advisor) REQUIRE a.name IS UNIQUE"
        ]

        for constraint in constraints:
            await client.execute_query(constraint)

        # Sample data - create deals
        await client.execute_query("""
            CREATE (d:Deal {
                id: 'sample-deal-1',
                title: 'Tech Corp Acquisition',
                description: 'Acquisition using Section 338(h)(10) election',
                value: 250000000,
                date: date('2024-02-15'),
                created_at: datetime()
            })
        """)

        # Create election
        await client.execute_query("""
            CREATE (e:Election {
                id: 'sample-election-1',
                type: '338(h)(10)',
                section: '338(h)(10)',
                filing_deadline: date('2024-08-15'),
                description: 'Partnership basis step-up election'
            })
        """)

        # Create party
        await client.execute_query("""
            CREATE (p:Party {
                name: 'Tech Solutions LLC',
                type: 'Target',
                jurisdiction: 'Delaware',
                tax_status: 'LLC'
            })
        """)

        # Create relationships
        await client.execute_query("""
            MATCH (d:Deal {id: 'sample-deal-1'}), (e:Election {id: 'sample-election-1'})
            CREATE (d)-[:INVOLVES]->(e)
        """)

        await client.execute_query("""
            MATCH (d:Deal {id: 'sample-deal-1'}), (p:Party {name: 'Tech Solutions LLC'})
            CREATE (d)-[:HAS_PARTY]->(p)
        """)

        logger.info("✅ Successfully populated Neo4j with sample data.")

        # Test the populated data
        network = await client.get_deal_network('sample-deal-1')
        logger.info(f"🔍 Test deal network query returned: {len(network)} entities.")

        return True
    except Exception as e:
        logger.error(f"❌ Failed to populate Neo4j: {e}")
        return False
    finally:
        if client and client.driver:
            await client.close()

async def show_database_status():
    """Show current database status and statistics."""
    logger.info("📊 Database Status Report")
    logger.info("=" * 50)

    # Supabase status
    try:
        settings = Settings()
        store = SupabaseVectorStore(settings)
        results = await store.search("", 100)  # Get all documents
        logger.info(f"📋 Supabase: {len(results)} documents")
    except Exception as e:
        logger.info(f"📋 Supabase: Connection failed - {e}")

    # Neo4j status
    neo4j_client = None
    try:
        neo4j_client = Neo4jClient(settings)
        await neo4j_client.connect()

        # Count nodes by type
        node_types = await neo4j_client.execute_query("""
            MATCH (n) RETURN labels(n) as labels, count(*) as count
        """)

        logger.info("🕸️  Neo4j nodes by type:")
        for row in node_types:
            if row['labels']:
                logger.info(f"   - {row['labels'][0]}: {row['count']}")

        # Count relationships
        rel_count = await neo4j_client.execute_query("""
            MATCH ()-[r]-() RETURN count(r) as rel_count
        """)
        logger.info(f"   - Total relationships: {rel_count[0]['rel_count']}")

    except Exception as e:
        logger.info(f"🕸️  Neo4j: Connection failed - {e}")
    finally:
        if neo4j_client and neo4j_client.driver:
            await neo4j_client.close()

async def main():
    """Main function to run database setup and tests."""
    logger.info("🚀 Tax Intelligence Platform Database Setup")
    logger.info("=" * 60)

    # Test connections first
    logger.info("\n1️⃣  Testing Database Connections...")
    supabase_ok = await test_supabase_connection()
    neo4j_ok = await test_neo4j_connection()

    if not supabase_ok and not neo4j_ok:
        logger.error("❌ Both databases failed to connect. Please check your setup.")
        return

    # Offer to populate databases
    logger.info("\n2️⃣  Database Population Options:")

    if supabase_ok:
        logger.info("🗂️  Supabase is connected.")
        populate_supabase = input("Populate Supabase with sample tax documents? (y/n): ").lower().strip()
        if populate_supabase == 'y':
            await populate_supabase_sample()

    if neo4j_ok:
        logger.info("🕷️  Neo4j is connected.")
        populate_neo4j = input("Populate Neo4j with sample deal network? (y/n): ").lower().strip()
        if populate_neo4j == 'y':
            await populate_neo4j_sample()

    # Show final status
    logger.info("\n3️⃣  Final Database Status:")
    await show_database_status()

    logger.info("\n✅ Database setup complete!")
    logger.info("🔧 You can now start your RAG API server with: python -m uvicorn main:app --reload")

if __name__ == "__main__":
    asyncio.run(main())

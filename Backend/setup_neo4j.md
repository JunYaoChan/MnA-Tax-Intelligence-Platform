# Neo4j Setup Guide for Tax Intelligence Platform

## Overview

This guide will help you set up Neo4j to work with your Tax Intelligence Platform for precedent analysis and deal networks.

## Prerequisites

- Neo4j instance (you already have the project at `neo4j+s://21729c74.databases.neo4j.io`)
- Your credentials are already configured in `.env`: `neo4j` / `TnKp6GixjRuJ75dX4XBfA7kGePkdHcqr2CZLkv4rOxw`

## Step 1: Access Neo4j Browser

1. Go to your Neo4j instance dashboard at: `https://console.neo4j.io`
2. Find your project: `21729c74`
3. Click **Open** to access Neo4j Browser
4. Sign in with your credentials:
   - Username: `neo4j`
   - Password: `TnKp6GixjRuJ75dX4XBfA7kGePkdHcqr2CZLkv4rOxw`

## Step 2: Create Database Schema

1. In Neo4j Browser, run the following Cypher commands in order:

### Create Constraints for Unique IDs

```cypher
CREATE CONSTRAINT deal_id_unique IF NOT EXISTS
FOR (d:Deal) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT election_id_unique IF NOT EXISTS
FOR (e:Election) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT party_name_unique IF NOT EXISTS
FOR (p:Party) REQUIRE p.name IS UNIQUE;

CREATE CONSTRAINT advisor_name_unique IF NOT EXISTS
FOR (a:Advisor) REQUIRE a.name IS UNIQUE;

CREATE CONSTRAINT document_id_unique IF NOT EXISTS
FOR (doc:Document) REQUIRE doc.id IS UNIQUE;
```

### Create Index for Performance

```cypher
CREATE INDEX deal_date_index IF NOT EXISTS FOR (d:Deal) ON (d.date);
CREATE INDEX deal_value_index IF NOT EXISTS FOR (d:Deal) ON (d.value);
CREATE INDEX election_type_index IF NOT EXISTS FOR (e:Election) ON (e.type);
CREATE INDEX election_section_index IF NOT EXISTS FOR (e:Election) ON (e.section);
```

## Step 3: Insert Sample Data

### Create Sample Deals

```cypher
CREATE (d1:Deal {
    id: "deal-001",
    title: "ACME Corporations Acquisition",
    description: "Acquisition of XYZ Manufacturing with Section 338(h)(10) election.",
    value: 150000000,
    date: date("2023-06-15"),
    created_at: datetime()
})
CREATE (d2:Deal {
    id: "deal-002",
    title: "TechCorp Partnership Distribution",
    description: "Partnership interest distribution with Section 754 election made unilaterally.",
    value: 50000000,
    date: date("2024-01-20"),
    created_at: datetime()
})
CREATE (d3:Deal {
    id: "deal-003",
    title: "Global Industries Merger",
    description: "Merger transaction involving Section 351 non-recognition treatment.",
    value: 750000000,
    date: date("2023-11-08"),
    created_at: datetime()
});
```

### Create Elections

```cypher
CREATE (e1:Election {
    id: "election-001",
    type: "338(h)(10)",
    section: "338(h)(10)",
    filing_deadline: date("2023-12-15"),
    description: "Partnership interest basis step-up election"
})
CREATE (e2:Election {
    id: "election-002",
    type: "754",
    section: "754",
    filing_deadline: date("2024-02-15"),
    description: "Optional basis adjustment election"
})
CREATE (e3:Election {
    id: "election-003",
    type: "351",
    section: "351",
    filing_deadline: date("2023-12-15"),
    description: "Tax-free exchange of property"
});
```

### Create Parties

```cypher
CREATE (p1:Party {
    name: "ACME Corporation",
    type: "Buyer",
    jurisdiction: "Delaware",
    tax_status: "C-Corporation"
})
CREATE (p2:Party {
    name: "XYZ Manufacturing LLC",
    type: "Target",
    jurisdiction: "California",
    tax_status: "LLC"
})
CREATE (p3:Party {
    name: "TechCorp Partners LLP",
    type: "Partnership",
    jurisdiction: "New York",
    tax_status: "LP"
})
CREATE (p4:Party {
    name: "Global Industries Inc",
    type: "Acquirer",
    jurisdiction: "Texas",
    tax_status: "C-Corporation"
});
```

### Create Advisors

```cypher
CREATE (a1:Advisor {
    name: "Smith & Associates LLP",
    type: "Tax Advisor",
    specialization: "Corporate Tax"
})
CREATE (a2:Advisor {
    name: "Johnson Consulting LLC",
    type: "Financial Advisor",
    specialization: "M&A"
})
CREATE (a3:Advisor {
    name: "Davis Law Firm",
    type: "Legal Counsel",
    specialization: "Tax Law"
});
```

### Create Relationships

```cypher
// Link deals to elections
MATCH (d1:Deal {id:"deal-001"}), (e1:Election {id:"election-001"})
CREATE (d1)-[:INVOLVES]->(e1);

MATCH (d2:Deal {id:"deal-002"}), (e2:Election {id:"election-002"})
CREATE (d2)-[:INVOLVES]->(e2);

MATCH (d3:Deal {id:"deal-003"}), (e3:Election {id:"election-003"})
CREATE (d3)-[:INVOLVES]->(e3);

// Link deals to parties
MATCH (d1:Deal {id:"deal-001"}), (p1:Party {name:"ACME Corporation"})
CREATE (d1)-[:HAS_PARTY]->(p1);

MATCH (d1:Deal {id:"deal-001"}), (p2:Party {name:"XYZ Manufacturing LLC"})
CREATE (d1)-[:HAS_PARTY]->(p2);

MATCH (d2:Deal {id:"deal-002"}), (p3:Party {name:"TechCorp Partners LLP"})
CREATE (d2)-[:HAS_PARTY]->(p3);

MATCH (d3:Deal {id:"deal-003"}), (p4:Party {name:"Global Industries Inc"})
CREATE (d3)-[:HAS_PARTY]->(p4);

// Link deals to advisors
MATCH (d1:Deal {id:"deal-001"}), (a1:Advisor {name:"Smith & Associates LLP"})
CREATE (d1)-[:HAS_ADVISOR]->(a1);

MATCH (d2:Deal {id:"deal-002"}), (a2:Advisor {name:"Johnson Consulting LLC"})
CREATE (d2)-[:HAS_ADVISOR]->(a2);

MATCH (d3:Deal {id:"deal-003"}), (a3:Advisor {name:"Davis Law Firm"})
CREATE (d3)-[:HAS_ADVISOR]->(a3);

// Create precedent relationships
MATCH (d2:Deal {id:"deal-002"}), (d1:Deal {id:"deal-001"})
CREATE (d2)-[:REFERENCES]->(d1);
```

## Step 4: Verify Setup

### Run these queries to verify your data:

```cypher
// Check total nodes
MATCH (n) RETURN labels(n) as labels, count(*) as count

// Find deals with their elections
MATCH (d:Deal)-[:INVOLVES]->(e:Election)
RETURN d.id, d.title, e.type, e.section
ORDER BY d.date DESC

// Find similar deals
MATCH (d:Deal)-[:INVOLVES]->(e:Election {type: "338(h)(10)"})
RETURN d.id, d.title, d.value, d.date
ORDER BY d.value DESC

// Get deal network
MATCH (d:Deal {id: "deal-001"})-[:HAS_PARTY]->(p:Party),
      (d)-[:HAS_ADVISOR]->(a:Advisor),
      (d)-[:INVOLVES]->(e:Election)
RETURN d.title, collect(p.name) as parties,
       collect(a.name) as advisors,
       e.type as election
```

## Step 5: Advanced Queries for Testing

### Find Recent Similar Transactions

```cypher
MATCH (d:Deal)-[:INVOLVES]->(e:Election)
WHERE e.type = "338(h)(10)"
AND d.value >= 100000000
AND d.date >= date("2023-01-01")
OPTIONAL MATCH (d)-[:HAS_PARTY]->(p:Party)
OPTIONAL MATCH (d)-[:HAS_ADVISOR]->(a:Advisor)
RETURN d.id, d.title, d.value, d.date,
       collect(DISTINCT p.name) as parties,
       collect(DISTINCT a.name) as advisors
ORDER BY d.date DESC
LIMIT 5;
```

### Analyze Advisor Network

```cypher
MATCH (a:Advisor)<-[:HAS_ADVISOR]-(d:Deal)-[:INVOLVES]->(e:Election)
RETURN a.name, a.specialization, e.type,
       count(d) as deal_count,
       sum(d.value) as total_value
ORDER BY total_value DESC;
```

### Party Involvement Analysis

```cypher
MATCH (p:Party)<-[:HAS_PARTY]-(d:Deal)-[:INVOLVES]->(e:Election)
RETURN p.name, p.jurisdiction, e.type,
       count(d) as transactions,
       collect(DISTINCT d.title) as deal_titles
ORDER BY transactions DESC;
```

## Step 6: Test Your Code Integration

Once your database is populated, test these functions in your application:

```python
# Test Neo4j connection
neo4j_client = Neo4jClient(settings)
await neo4j_client.connect()

# Test deal network query
network = await neo4j_client.get_deal_network("deal-001")
print(f"Deal network: {network}")

# Test similar deals search
similar_deals = await neo4j_client.find_similar_deals({
    "election_type": "338(h)(10)",
    "min_value": 100000000,
    "min_date": "2023-01-01"
}, limit=5)
print(f"Similar deals found: {len(similar_deals)}")
```

## Troubleshooting

### Connection Issues:

- Verify your Neo4j URI is correct: `neo4j+s://21729c74.databases.neo4j.io`
- Check username/password credentials
- Ensure Neo4j instance is running

### Data Not Appearing:

- Run the constraint and data creation scripts in order
- Use Neo4j Browser to query data: `MATCH (d:Deal) RETURN d`
- Check for typos in Cypher queries

### Query Performance:

- Indexes are automatically created for constraints
- Additional indexes improve SELECT query performance
- For large datasets, consider query optimization and pagination

## Node Labels and Properties Reference

### Deal Node Properties:

- `id` (string): Unique identifier
- `title` (string): Deal title/description
- `description` (string): Detailed deal information
- `value` (number): Transaction value in dollars
- `date` (date): Transaction date
- `created_at` (datetime): Record creation timestamp

### Election Node Properties:

- `id` (string): Unique identifier
- `type` (string): Election type (e.g., "338(h)(10)", "754")
- `section` (string): IRC section
- `filing_deadline` (date): When election must be filed
- `description` (string): Election description

### Party Node Properties:

- `name` (string): Party/entity name
- `type` (string): "Buyer", "Target", "Partnership", etc.
- `jurisdiction` (string): State/incorporation location
- `tax_status` (string): Tax classification

### Advisor Node Properties:

- `name` (string): Advisor firm name
- `type` (string): "Tax Advisor", "Legal Counsel", "Financial Advisor"
- `specialization` (string): Area of expertise

## Relationships:

- `Deal-[:INVOLVES]->Election`
- `Deal-[:HAS_PARTY]->Party`
- `Deal-[:HAS_ADVISOR]->Advisor`
- `Deal-[:REFERENCES]->Deal` (for precedent relationships)

Your Neo4j setup for tax precedent analysis is now complete! 🚀

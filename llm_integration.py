from neo4j import GraphDatabase
from pathlib import Path
import os
from dotenv import load_dotenv
import openai
import tkinter as tk
from tkinter import scrolledtext

dotenv_path = Path('~/.env').expanduser()
load_dotenv(dotenv_path=dotenv_path)  

# Get variables
POKEDEX_URI = os.getenv('POKEDEX_URI')
POKEDEX_USER = os.getenv('POKEDEX_USER')
POKEDEX_PASSWORD = os.getenv('POKEDEX_PASSWORD')
#database_name = os.getenv('DATABASE_NAME')

driver = GraphDatabase.driver(POKEDEX_URI, auth=(POKEDEX_USER, POKEDEX_PASSWORD))
driver.verify_connectivity()




def get_graph_schema():
    schema = {}
    with driver.session() as session:
        # Node properties
        node_props = session.run("""
            CALL db.schema.nodeTypeProperties()
            YIELD nodeLabels, propertyName, propertyTypes
            RETURN nodeLabels, propertyName, propertyTypes
        """).data()
        
        # Relationship properties
        rel_props = session.run("""
            CALL db.schema.relTypeProperties()
            YIELD relType, propertyName, propertyTypes
            RETURN relType, propertyName, propertyTypes
        """).data()
        
        schema["nodes"] = node_props
        schema["relationships"] = rel_props
    return schema

client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def ask_gpt4o(prompt):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content

def run_cypher(query):
    with driver.session() as session:
        return session.run(query).data()

def question_to_cypher_and_answer(question):
    # prompt LLM to translate the question into a Cypher query

    schema = get_graph_schema()
    
    prompt = f"""
    You are a Cypher expert. Here is the schema of the graph database: 
    {schema}
    Given the following question, respond ONLY with the Cypher query. Take into account the schema you have to figure out what the node, relationship and property names are.
    Do NOT include markdown or code block formatting. Just return the plain Cypher.

    Question: "{question}"
    """
    cypher_query = ask_gpt4o(prompt)
    print("Generated Cypher Query:\n", cypher_query)

    results = run_cypher(cypher_query)
    print("Query Results:\n", results)

    interpretation_prompt = f"""
    Given the question: "{question}"
    And the results: {results}
    List the results. Do not interpret them and do not check whether their are factually correct.
    """
    explanation = ask_gpt4o(interpretation_prompt)
    return explanation
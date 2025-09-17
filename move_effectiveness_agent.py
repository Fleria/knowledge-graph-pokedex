from langgraph.prebuilt import create_react_agent
from neo4j import GraphDatabase,basic_auth
from pydantic import BaseModel, Field
from typing import Optional
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from typing import Annotated
from langgraph.prebuilt import InjectedState
from langgraph.graph import MessagesState
import os
import re
import csv
from io import StringIO
from neo4j import GraphDatabase
from pathlib import Path
import os
from dotenv import load_dotenv
import openai
from neo4j_graphrag.schema import get_schema

dotenv_path = Path('~/.env').expanduser()
load_dotenv(dotenv_path=dotenv_path)  

# Get variables
POKEDEX_URI = os.getenv('POKEDEX_URI')
POKEDEX_USER = os.getenv('POKEDEX_USER')
POKEDEX_PASSWORD = os.getenv('POKEDEX_PASSWORD')


def schema_retriever():
    """
    Gets the schema from the database. 
    """
    driver = GraphDatabase.driver(POKEDEX_URI, auth=basic_auth(POKEDEX_USER, POKEDEX_PASSWORD) )
    schema = get_schema(driver, is_enhanced = False, sanitize = False)
    
    return {"schema": schema}


@tool
def move_effectiveness_calculator(
    question: str,
    state: Annotated[MessagesState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """
    Calculate move type effectiveness against single- and dual-type Pokémon using the neo4j database.
    """

    all_type_dictionary = {
        "Normal": {
            "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1,
            "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1, "Psychic": 1, "Bug": 1,
            "Rock": 0.5, "Ghost": 0, "Dragon": 1, "Dark": 1, "Steel": 0.5, "Fairy": 1
        },
        "Fire": {
            "Normal": 1, "Fire": 0.5, "Water": 0.5, "Electric": 1, "Grass": 2, "Ice": 2,
            "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1, "Psychic": 1, "Bug": 2,
            "Rock": 0.5, "Ghost": 1, "Dragon": 0.5, "Dark": 1, "Steel": 2, "Fairy": 1
        },
        "Water": {
            "Normal": 1, "Fire": 2, "Water": 0.5, "Electric": 1, "Grass": 0.5, "Ice": 1,
            "Fighting": 1, "Poison": 1, "Ground": 2, "Flying": 1, "Psychic": 1, "Bug": 1,
            "Rock": 2, "Ghost": 1, "Dragon": 0.5, "Dark": 1, "Steel": 1, "Fairy": 1
        },
        "Electric": {
            "Normal": 1, "Fire": 1, "Water": 2, "Electric": 0.5, "Grass": 0.5, "Ice": 1,
            "Fighting": 1, "Poison": 1, "Ground": 0, "Flying": 2, "Psychic": 1, "Bug": 1,
            "Rock": 1, "Ghost": 1, "Dragon": 0.5, "Dark": 1, "Steel": 1, "Fairy": 1
        },
        "Grass": {
            "Normal": 1, "Fire": 0.5, "Water": 2, "Electric": 1, "Grass": 0.5, "Ice": 1,
            "Fighting": 1, "Poison": 0.5, "Ground": 2, "Flying": 0.5, "Psychic": 1, "Bug": 0.5,
            "Rock": 2, "Ghost": 1, "Dragon": 0.5, "Dark": 1, "Steel": 0.5, "Fairy": 1
        },
        "Ice": {
            "Normal": 1, "Fire": 0.5, "Water": 0.5, "Electric": 1, "Grass": 2, "Ice": 0.5,
            "Fighting": 1, "Poison": 1, "Ground": 2, "Flying": 2, "Psychic": 1, "Bug": 1,
            "Rock": 1, "Ghost": 1, "Dragon": 2, "Dark": 1, "Steel": 0.5, "Fairy": 1
        },
        "Fighting": {
            "Normal": 2, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 2,
            "Fighting": 1, "Poison": 0.5, "Ground": 1, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5,
            "Rock": 2, "Ghost": 0, "Dragon": 1, "Dark": 2, "Steel": 2, "Fairy": 0.5
        },
        "Poison": {
            "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 2, "Ice": 1,
            "Fighting": 1, "Poison": 0.5, "Ground": 0.5, "Flying": 1, "Psychic": 1, "Bug": 1,
            "Rock": 0.5, "Ghost": 0.5, "Dragon": 1, "Dark": 1, "Steel": 0, "Fairy": 2
        },
        "Ground": {
            "Normal": 1, "Fire": 2, "Water": 1, "Electric": 2, "Grass": 0.5, "Ice": 1,
            "Fighting": 1, "Poison": 2, "Ground": 1, "Flying": 0, "Psychic": 1, "Bug": 0.5,
            "Rock": 2, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 2, "Fairy": 1
        },
        "Flying": {
            "Normal": 1, "Fire": 1, "Water": 1, "Electric": 0.5, "Grass": 2, "Ice": 1,
            "Fighting": 2, "Poison": 1, "Ground": 1, "Flying": 1, "Psychic": 1, "Bug": 2,
            "Rock": 0.5, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 0.5, "Fairy": 1
        },
        "Psychic": {
            "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1,
            "Fighting": 2, "Poison": 2, "Ground": 1, "Flying": 1, "Psychic": 0.5, "Bug": 1,
            "Rock": 1, "Ghost": 1, "Dragon": 1, "Dark": 0, "Steel": 0.5, "Fairy": 1
        },
        "Bug": {
            "Normal": 1, "Fire": 0.5, "Water": 1, "Electric": 1, "Grass": 2, "Ice": 1,
            "Fighting": 0.5, "Poison": 0.5, "Ground": 1, "Flying": 0.5, "Psychic": 2, "Bug": 1,
            "Rock": 1, "Ghost": 0.5, "Dragon": 1, "Dark": 2, "Steel": 0.5, "Fairy": 0.5
        },
        "Rock": {
            "Normal": 1, "Fire": 2, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 2,
            "Fighting": 0.5, "Poison": 1, "Ground": 0.5, "Flying": 2, "Psychic": 1, "Bug": 2,
            "Rock": 1, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 0.5, "Fairy": 1
        },
        "Ghost": {
            "Normal": 0, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1,
            "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1, "Psychic": 2, "Bug": 1,
            "Rock": 1, "Ghost": 2, "Dragon": 1, "Dark": 0.5, "Steel": 1, "Fairy": 1
        },
        "Dragon": {
            "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1,
            "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1, "Psychic": 1, "Bug": 1,
            "Rock": 1, "Ghost": 1, "Dragon": 2, "Dark": 1, "Steel": 0.5, "Fairy": 0
        },
        "Dark": {
            "Normal": 1, "Fire": 1, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1,
            "Fighting": 0.5, "Poison": 1, "Ground": 1, "Flying": 1, "Psychic": 2, "Bug": 1,
            "Rock": 1, "Ghost": 2, "Dragon": 1, "Dark": 0.5, "Steel": 1, "Fairy": 0.5
        },
        "Steel": {
            "Normal": 1, "Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Grass": 1, "Ice": 2,
            "Fighting": 1, "Poison": 1, "Ground": 1, "Flying": 1, "Psychic": 1, "Bug": 1,
            "Rock": 2, "Ghost": 1, "Dragon": 1, "Dark": 1, "Steel": 0.5, "Fairy": 2
        },
        "Fairy": {
            "Normal": 1, "Fire": 0.5, "Water": 1, "Electric": 1, "Grass": 1, "Ice": 1,
            "Fighting": 2, "Poison": 0.5, "Ground": 1, "Flying": 1, "Psychic": 1, "Bug": 1,
            "Rock": 1, "Ghost": 1, "Dragon": 2, "Dark": 2, "Steel": 0.5, "Fairy": 1
        }
    }
    driver = GraphDatabase.driver(POKEDEX_URI, auth=(POKEDEX_USER, POKEDEX_PASSWORD))

    # Cypher query: fetch 'factor' property of EFFECTIVENESS relationships in neo4j graph
    query = """ MATCH (m1:Move {name: $name1})-[:HAS_TYPE]->(t1:Type)-[r:EFFECTIVENESS]-(t2:Type)<-[:HAS_TYPE]-(m2:Move {name: $name2})
    RETURN r.factor AS factor
    """

    records, _, _ = driver.execute_query(
        query,
        titles=activity_titles,
        age=age_group,
        database_=database_name,
    )

    results = []
    for r in records:
        path = r['path']
        for i in range(len(path.relationships)):
            from_node = path.nodes[i]['title']
            to_node = path.nodes[i + 1]['title']
            rel_type = path.relationships[i].type
            age = path.nodes[i]['age']
            results.append(f"({from_node}) -[{rel_type}]-> ({to_node}) [age: {age}]")

    return {
        "tool_call_id": tool_call_id,
        "name": "recommend_learning_path",
        "content": results if results else "No connected activities found."
    }




def move_effectiveness_agent():
    return create_react_agent(
    model="openai:gpt-4.1",
    tools=[move_effectiveness_calculator],
    prompt=RECOMMENDER_AGENT_PROMT,
    name="activities_recommender",
)
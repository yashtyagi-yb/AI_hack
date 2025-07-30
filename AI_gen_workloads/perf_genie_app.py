from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.agents import AgentExecutor, create_openai_functions_agent
from perf_service_tools import run_test_tool, get_test_status_tool, get_test_report_tool
import json
import ai_system_instructions
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import nest_asyncio
from fastapi.middleware.cors import CORSMiddleware
from database.aeon_database_util import create_user, store_chat, get_chat, get_chats_history

load_dotenv()

tools = [run_test_tool, get_test_status_tool, get_test_report_tool]

llm = ChatOpenAI(
    model="gpt-4.1",
    max_retries=2,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

def fetch_all_yaml_from_github_dir(owner, repo, folder_path, branch="main"):

    yamls = []

    for folder in folder_path:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{folder}?ref={branch}"
        headers = {"Accept": "application/vnd.github.v3+json"}

        response = requests.get(api_url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch directory: {response.status_code} — {response.text}")

        files = response.json()

        for file in files:
            if file['name'].endswith('.yaml') or file['name'].endswith('.yml'):
                raw_url = file['download_url']
                raw_response = requests.get(raw_url)
                if raw_response.status_code == 200:
                    content = raw_response.text
                    yamls.append({file['name']: content})
                else:
                    print(f"Failed to fetch {file['name']}: {raw_response.status_code}")

    return yamls

yaml_dirs = ["config/yugabyte/regression_pipelines/foreign_key/", "config/yugabyte/regression_pipelines/miscellaneous/yugabyte"]

yamls = fetch_all_yaml_from_github_dir("yugabyte", "benchbase",
                                       yaml_dirs)
all_yamls=yamls

SYSTEM_INSTRUCTIONS = ai_system_instructions.INSTRUCTIONS

def create_chains_for_session():
    global memo
    memo = ConversationBufferMemory(memory_key="chat_history",return_messages=True)

    yaml_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INSTRUCTIONS),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    yaml_prompt_with_yamls = yaml_prompt.partial(all_yamls=all_yamls)

    agent = create_openai_functions_agent(llm=llm, prompt=yaml_prompt_with_yamls, tools=[run_test_tool, get_test_status_tool])

    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=[run_test_tool, get_test_status_tool],
        memory=memo,
        verbose=True
    )

    return {"agent_executor": agent_executor}

def get_chains_for_session(session_id, user_sessions):
    if session_id not in user_sessions:
        user_sessions[session_id] = create_chains_for_session()
    return user_sessions[session_id]

nest_asyncio.apply()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_store = {}
saved_yb_yaml = ''
saved_pg_yaml = ''

class QueryInput(BaseModel):
    session_id: str
    query: str

@app.post("/refresh")
async def refresh_memory(input: QueryInput):
    global saved_yb_yaml, saved_pg_yaml
    saved_yb_yaml = ''
    saved_pg_yaml = ''
    data = json.loads(input.query)
    print(input.query, data['chat_id'])
    response = llm.invoke(
            f"You need to give a relevant name to the chat from user. Do not use database name. Here's the input : {str(data['messages'])}. Use only user messages to name the chat. In case no technical chat has happened, name it relevantly. Keep the name short and crisp. Output **only** the name.")
    chat_id = store_chat(str(data['chat_id']), response.content, str(data['acc_id']), data['messages'],
                             data['saved_yb_yamls'], data['saved_pg_yamls'])
    print(chat_id['data'], input.session_id)
    if chat_id['data']!=data['chat_id']:
        session_store[chat_id['data']]=session_store.get(input.session_id)
        session_store.pop(input.session_id)
    return JSONResponse(
            content={"text": response.content, "chat_id": chat_id},
            status_code=200
    )

@app.post("/login")
async def login(input: QueryInput):
    data=json.loads(input.query)
    output=create_user(data['username'],data['password'])
    print(output)
    return JSONResponse(
        content={"success": output['success'], 'message': output['message'], 'data': output['data']},
        status_code=200
    )

@app.post("/get-chat-history")
async def get_chat_history(input: QueryInput):
    id = json.loads(input.query)['id']
    print(json.loads(input.query))
    output = get_chats_history(id)
    return JSONResponse(
        content={"success": output['success'], 'message': output['message'], 'data': output['data']},
        status_code=200
    )

@app.post("/open-chat")
async def open_chat(input: QueryInput):
    output=get_chat(input.query)
    return JSONResponse(
        content={"success": output['success'], 'message': output['message'], 'data': output['data']},
        status_code=200
    )

@app.post("/gen_yaml")
async def gen_yaml(input: QueryInput):

    global saved_yb_yaml , saved_pg_yaml
    print(input.session_id)
    chain = get_chains_for_session(input.session_id, session_store)
    agent_executor = chain['agent_executor']

    query_text = input.query

    if not isinstance(query_text, str) or not query_text.strip():
        return JSONResponse(content={"error": "'query' must be a non-empty string"}, status_code=400)

    agent_output = agent_executor.invoke({"input": query_text})
    output = agent_output.get("output") or agent_output.get("text")

    response = llm.invoke(
        f"Check whether this output contains a YAML file or not. Here's the output : {output}. Answer **only** either 'Yes' or 'No'"
    )

    if response.content.strip().lower() == "yes":
        saved_yb_yaml = output[output.index('###') + 3:output.rindex('###')]
        saved_pg_yaml = output[output.index('$$$') + 3:output.rindex('$$$')]
        output = output[:output.index('###')] + output[output.rindex('$$$') + 3:]

    return JSONResponse(
        content={"text": output, "yb_yaml": saved_yb_yaml, "pg_yaml": saved_pg_yaml},
        status_code=200
    )

uvicorn.run(app, host="0.0.0.0", port=3032)
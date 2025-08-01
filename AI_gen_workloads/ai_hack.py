from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain, SequentialChain, ConversationChain
from langchain.memory import ConversationBufferMemory
import json
import system_req
import configparser
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
from perf_service_util import PerfServiceClient
from database.aeon_database_util import create_user, store_chat, get_chat

import configparser

load_dotenv()

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

SYSTEM_INSTRUCTIONS = system_req.INSTRUCTIONS

def create_chains_for_session():
    global memo
    memo = ConversationBufferMemory(k=4)

    yaml_prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_INSTRUCTIONS)
    ])

    yaml_prompt_with_yamls = yaml_prompt.partial(all_yamls=all_yamls)

    pipeline = LLMChain(
        llm=llm,
        prompt=yaml_prompt_with_yamls,
        memory=memo,
        verbose=False
    )

    return {"pipeline": pipeline}

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
config = configparser.ConfigParser()
config.read('config.properties')
global client_yb, client_pg
client_yb = PerfServiceClient(config['YB']['endpoint'], config['YB']['username'], config['YB']['password'],
                              config['YB']['client_ip_addr'],config['YB']['provider'])
client_pg = PerfServiceClient(config['PG']['endpoint'], config['PG']['username'], config['PG']['password'],
                              config['PG']['client_ip_addr'],config['PG']['provider'])


class QueryInput(BaseModel):
    session_id: str
    query: str

@app.post("/login")
async def login(input: QueryInput):
    data=json.loads(input.query)
    output=create_user(data['username'],data['password'])
    return JSONResponse(
        content={"success": output['success'], 'message': output['message'], 'data': output['data']},
        status_code=200
    )

@app.post("/open-chat")
async def open_chat(input: QueryInput):
    global saved_yb_yaml, saved_pg_yaml
    saved_yb_yaml = ''
    saved_pg_yaml = ''
    output=get_chat(input.query)
    return JSONResponse(
        content={"success": output['success'], 'message': output['message'], 'data': output['data']},
        status_code=200
    )

@app.post("/refresh")
async def refresh_memory(input: QueryInput):
    global saved_yb_yaml, saved_pg_yaml
    saved_yb_yaml = ''
    saved_pg_yaml = ''
    data=json.loads(input.query)
    print(data['messages'])
    chain = get_chains_for_session(input.session_id, session_store)
    if chain.get("pipeline") and hasattr(chain["pipeline"], "memory"):
        chain["pipeline"].memory.clear()
    print(input.query, data['chat_id'])
    response = llm.invoke(
        f"You need to give a relevant name to the chat from user. Here's the input : {str(data['messages'])}. Use only user messages to name the chat. In case no technical chat has happened, name it relevantly. Keep the name short and crisp. Output **only** the name.")
    chat_id=store_chat(str(data['chat_id']),response.content,str(data['username']),data['messages'],data['saved_yb_yamls'],data['saved_pg_yamls'])
    print(chat_id)
    return JSONResponse(
        content={"text": response.content,"chat_id":chat_id},
        status_code=200
    )

@app.post("/gen_yaml")
async def gen_yaml(input: QueryInput):
    global saved_yb_yaml , saved_pg_yaml
    chain = get_chains_for_session(input.session_id, session_store)

    pipeline = chain['pipeline']

    query_text = input.query

    if not isinstance(query_text, str) or not query_text.strip():
        return JSONResponse(content={"error": "'query' must be a non-empty string"}, status_code=400)

    response = llm.invoke(
        f"Check whether this input contains a test id to get status for a test. Here's the input : {query_text.strip()}. If YES answer **only** test id otherwise 0"
    )

    if(response.content != "0"):
        yb_output=client_yb.get_test_status(response.content)
        pg_output = client_pg.get_test_status(response.content)
        return JSONResponse(
            content={"text": yb_output+"\n"+pg_output, "yb_yaml": saved_yb_yaml, "pg_yaml": saved_pg_yaml},
            status_code=200
        )

    yaml_output = pipeline.invoke({"input": query_text.strip()})
    output = yaml_output['text']
    print(output)

    response = llm.invoke(
        f"Check whether this output contains a YAML file or not. Here's the output : {output}. Answer **only** either 'Yes' or 'No'"
    )

    print(response.content)

    if response.content.strip() == "Yes":
        saved_yb_yaml = output[output.index('###') + 3:output.rindex('###')]
        saved_pg_yaml = output[output.index('$$$') + 3:output.rindex('$$$')]
        output = output[:output.index('###')] + output[output.rindex('$$$') + 3:]

    if "Running your workload..." in output:
        print(saved_yb_yaml)
        print(saved_pg_yaml)

        config = configparser.ConfigParser()
        config.read('config.properties')
        client_yb = PerfServiceClient(config['YB']['endpoint'], config['YB']['username'], config['YB']['password'],
                                      config['YB']['client_ip_addr'],config['YB']['provider'])
        client_pg = PerfServiceClient(config['PG']['endpoint'], config['PG']['username'], config['PG']['password'],
                                      config['PG']['client_ip_addr'],config['PG']['provider'])
        test_id_yb,msg = client_yb.run_test(saved_yb_yaml)
        print(msg)
        test_id_pg,msg = client_pg.run_test(saved_pg_yaml)
        print(msg)

        #print(client_yb.get_test_status(test_id_yb, test_id_pg))
        #print(client_yb.get_test_status(test_id_yb, test_id_pg))

    print(output)
    return JSONResponse(
        content={"text": output, "yb_yaml": saved_yb_yaml, "pg_yaml": saved_pg_yaml},
        status_code=200
    )


uvicorn.run(app, host="0.0.0.0", port=3032)
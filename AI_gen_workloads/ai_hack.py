from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain, SequentialChain, ConversationChain
from langchain.memory import ConversationBufferMemory
import yaml, json
import system_req

from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
import requests
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
import uvicorn
import nest_asyncio
from fastapi.middleware.cors import CORSMiddleware
from perf_service_util import PerfServiceClient
from yugabyte_simple_python_app.sample_app import create_user, create_database, store_chat

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


class QueryInput(BaseModel):
    session_id: str
    query: str

@app.post("/login")
async def login(input: QueryInput):
    data=json.loads(input.query)
    output=create_user(input.session_id,data['username'],data['password'])
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
    print(input.query)
    response = llm.invoke(
        f"You need to give a relevant name to the chat from user. Here's the input : {str(data['messages'])}. Use only user messages to name the chat. In case no technical chat has happened, name it relevantly. Keep the name short and crisp. Output **only** the name.")
    store_chat(response.content,str(data['username']),str(data['messages']),str(data['saved_yb_yamls']),str(data['saved_pg_yamls']))
    return JSONResponse(
        content={"text": response.content},
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
        output=client.get_test_status(response.content)
        return JSONResponse(
            content={"text": output, "yb_yaml": saved_yb_yaml, "pg_yaml": saved_pg_yaml},
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
        client = PerfServiceClient()
        test_id = client.run_test(saved_yb_yaml)
        status,message = client.get_test_status(test_id)
        output=message
        print(message)

    print(output)
    return JSONResponse(
        content={"text": output, "yb_yaml": saved_yb_yaml, "pg_yaml": saved_pg_yaml},
        status_code=200
    )


uvicorn.run(app, host="0.0.0.0", port=3032)
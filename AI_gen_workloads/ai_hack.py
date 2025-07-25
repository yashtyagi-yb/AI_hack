from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain, SequentialChain, ConversationChain
from langchain.memory import ConversationBufferMemory
import yaml, json
import system_req
import configparser
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
saved_yaml = ''


class QueryInput(BaseModel):
    session_id: str
    query: str


@app.post("/refresh")
async def refresh_memory(input: QueryInput):
    global saved_yaml
    saved_yaml = ''
    chain = get_chains_for_session(input.session_id, session_store)
    if chain.get("pipeline") and hasattr(chain["pipeline"], "memory"):
        chain["pipeline"].memory.clear()
        return {"status": "success", "message": "Memory refreshed."}
    return {"status": "error", "message": "Memory not found."}


@app.post("/gen_yaml")
async def gen_yaml(input: QueryInput):
    global saved_yaml  # Declare to modify the global variable
    chain = get_chains_for_session(input.session_id, session_store)

    pipeline = chain['pipeline']

    query_text = input.query

    if not isinstance(query_text, str) or not query_text.strip():
        return JSONResponse(content={"error": "'query' must be a non-empty string"}, status_code=400)

    yaml_output = pipeline.invoke({"input": query_text.strip()})
    output = yaml_output['text']
    print(output)

    response = llm.invoke(
        f"Check whether this output contains a YAML file or not. Here's the output : {output}. Answer **only** either 'Yes' or 'No'"
    )

    print(response.content)

    if response.content.strip() == "Yes":
        saved_yaml = output[output.index('###') + 3:output.rindex('###')]
        output = output[:output.index('###')] + output[output.rindex('###') + 3:]

    if "Running your workload..." in output:
        config = configparser.ConfigParser()
        config.read('config.properties')
        saved_yb_yaml = ""
        saved_pg_yaml = ""
        client_yb = PerfServiceClient(config['YB']['endpoint'], config['YB']['username'], config['YB']['password'], config['YB']['client_ip_addr'])
        client_pg = PerfServiceClient(config['PG']['endpoint'], config['PG']['username'], config['PG']['password'], config['PG']['client_ip_addr'])
        test_id_yb = client_yb.run_test(saved_yb_yaml)
        test_id_pg = client_pg.run_test(saved_pg_yaml)
        message_yb = client_yb.get_test_status(test_id_yb)
        message_pg = client_yb.get_test_status(test_id_pg)
        client_yb.get_test_report(test_id_yb, test_id_pg)
        print(message_yb + message_pg)


    print(output)
    return JSONResponse(
        content={"text": output, "yaml": saved_yaml},
        status_code=200
    )


uvicorn.run(app, host="0.0.0.0", port=3032)
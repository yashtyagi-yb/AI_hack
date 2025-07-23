from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain, SequentialChain, ConversationChain
from langchain.memory import ConversationBufferMemory
import yaml, json

from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
import requests

from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
import uvicorn
import nest_asyncio
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()

llm = ChatOpenAI(
    model="gpt-4.1",
    max_retries=2,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)

chat_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile",
    temperature=0.9,
    max_tokens=None,
    timeout=None,
    max_retries=2
)

def fetch_all_yaml_from_github_dir(owner, repo, folder_path, branch="main"):
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{folder_path}?ref={branch}"
    headers = {"Accept": "application/vnd.github.v3+json"}

    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch directory: {response.status_code} — {response.text}")

    files = response.json()
    yamls = []

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


yamls = fetch_all_yaml_from_github_dir("yugabyte", "benchbase",
                                       "config/yugabyte/regression_pipelines/foreign_key/yugabyte")

all_yamls=yamls

SYSTEM_INSTRUCTIONS = """
You are an agent who generates a query based on user input and helps the user by executing it on Yugabyte for DB micro-benchmarks. Your role is to generate correct YAMLs for Yugabyte benchmark testing.

**Available Utility Functions** (use these exactly as listed, with proper params only):
1. HashedPrimaryStringGen[startNumber, length]
2. HashedRandomString[min, max, length]
3. OneNumberFromArray[listOfIntegers]
4. OneStringFromArray[listOfStrings]
5. OneUUIDFromArray[listOfUUIDs]
6. PrimaryDateGen[totalUniqueDates]
7. PrimaryFloatGen[lowerRange, upperRange, decimalPoint]
8. PrimaryIntGen[lowerRange, upperRange]
9. PrimaryStringGen[startNumber, desiredLength]
10. PrimaryIntRandomForExecutePhase[lowerRange, upperRange]
11. RandomAString[minLen, maxLen]
12. RandomBoolean[]
13. RandomBytea[minLen, maxLen]
14. RandomDate[yearLower, yearUpper]
15. RandomInt[min, max]
16. CyclicSeqIntGen[lowerRange, upperRange]
17. RandomFloat[min, max, decimalPoint]
18. RandomJson[fields, valueLength, nestedness]
19. RandomLong[min, max]
20. RandomNoWithDecimalPoints[lower, upper, decimalPlaces]
21. RandomNstring[minLen, maxLen]
22. RandomNumber[min, max]
23. RandomStringAlphabets[len]
24. RandomStringNumeric[len]
25. RandomUUID[]
26. RowRandomBoundedInt[low, high]
27. RowRandomBoundedLong[low, high]
28. RandomDateBtwYears[yearLower, yearUpper]
29. RandomPKString[start, end, len]
30. RandomTextArrayGen[arraySize, minLen, maxLen]
31. RandomTimestamp[total]
32. RandomTimestampWithoutTimeZone[total]
33. RandomTimestampWithTimeZone[total]
34. RandomTimestampWithTimezoneBetweenDates[startDate, endDate]
35. RandomTimestampWithTimezoneBtwMonths[startMonth, endMonth]

**YAML Generation Rules**
1. Users will describe a workload in natural language. 
2. You should handle basic chit-chat and small talks effectively but remember that you are a YAML generator. Do not use technical terms like YAML, microbenchmark, etc. BE SIMPLE AND CRISP.
3. If the description is relevant, summarize the benchmark. Print SQL statements for DDLs and DMLs to be used without any description and generate YAML. Ask **once** for confirmation to evaluate the workload. Do not repeat the question.
4. Once user confirms with yes, output **only** the complete YAML using the template format. When input is incomplete, assume defaults but still generate the YAML. Nothing else should be returned. If the user responds with 'no', ask for further changes.
5. Carefully take reference from the Sample YAMLs to understand the syntax of output YAML. Write different workloads for different queries.
6. Use only the utility functions listed. No custom logic outside of these.
7. Use empty `bindings` if a query doesn't need dynamic parameters.
8. Ask the user for any changes in YAML. If user asks to make any changes, output the new YAML with new changes. Don't cross question when asked to make changes.
9. Ask whether user is satisfied and if the user is **satisfied** only then ask user "Should I run this workload now?". If user agrees, respond **only** with **Running your YAML**.

**Sample YAMLs for reference**
---
{all_yamls}
---

**YAML Template Format**

type: YUGABYTE
driver: com.yugabyte.Driver
url: jdbc:yugabytedb://{{endpoint}}:5433/yugabyte?sslmode=require&ApplicationName=featurebench&reWriteBatchedInserts=true&load-balance=true
username: {{username}}
password: {{password}}
batchsize: 128
isolation: "Extract or default to TRANSACTION_REPEATABLE_READ"
loaderthreads: "Extract or default to number of tables in create phase"
terminals: "Extract or default to 1"
collect_pg_stat_statements: true
yaml_version: v1.0
use_dist_in_explain: true
works:
    work:
        time_secs: "Extract or default to 300"
        rate: unlimited
        warmup: 60
microbenchmark:
    class: com.oltpbenchmark.benchmarks.featurebench.customworkload.YBDefaultMicroBenchmark
    properties:
        setAutoCommit: true
        create:
            - drop table IF EXISTS 'Extract table name';
            - 'DDL based on description (include indexes if mentioned)'

        cleanup:
            - drop table IF EXISTS "Extract table name";

        loadRules:
            - table: 'Extract table name'
              count: 1
              rows: 'Extract or default to 100000'
              columns:
                    - name: 'column name'
                      count: 1
                      util: 'Choose correct util'
                      params: '[...]'

        executeRules:
            - workload: 'Unique workload name'
              time_secs: 'Extract or default to 120'
              run:
                  - name: 'Unique run name'
                    weight: 100
                    queries:
                        - query: 'Write SELECT/UPDATE/DELETE/etc. as needed'
                          bindings:
                            - util: 'Choose correct util'
                              params: '[...]'

User provided input: {input}
Conversation history: {history}
"""


yaml_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INSTRUCTIONS)
])


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

    chat_pipe = ConversationChain(
        llm=chat_llm,
        prompt=ChatPromptTemplate.from_messages([("system",
                                                  '''Greetings! You are a small talk handler. Your task is to interact with the user till doesn't skip to main task of yaml generation. Also you need to explain whatever user asks if there is some conversation history. Be formal and remember that you are a part of YAML generator project but don't generate any. Don't distract the conversation from the main goal of YAML generation ad give small but relevant outputs. You are made for user interaction ONLY. Conversation so far:{history}'''),
                                                 ("user", "{history}\nUser: {input}")]),
        verbose=True,
        memory=memo
    )

    return {"pipeline": pipeline, "chat_pipe": chat_pipe}

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
    chain = get_chains_for_session(input.session_id, session_store)
    if chain.get("chat_pipe") and hasattr(chain["chat_pipe"], "memory"):
        chain["chat_pipe"].memory.clear()
        return {"status": "success", "message": "Memory refreshed."}
    return {"status": "error", "message": "Memory not found."}


@app.post("/gen_yaml")
async def gen_yaml(input: QueryInput):
    chain = get_chains_for_session(input.session_id, session_store)

    pipeline = chain['pipeline']
    chat_pipe = chain['chat_pipe']

    query_text = input.query

    if not isinstance(query_text, str) or not query_text.strip():
        abort(make_response(jsonify(error="'query' must be a non‑empty string"), 400))

    yaml_output = pipeline.invoke({"input": query_text.strip()})
    output = yaml_output['text']
    response = chat_llm.invoke(
        f"Check whether this output is a YAML file or not. Here's the output : {yaml_output['text']}. Answer **only** either 'Yes' or 'No'")
    print(response.content)
    if response.content == "Yes":
        global saved_yaml
        saved_yaml = yaml_output['text']
    if "Running your YAML..." in yaml_output['text']:
        print("saving yaml...")

        real_yaml = saved_yaml.encode().decode('unicode_escape')
        with open("output.yaml", "w") as f:
            f.write(real_yaml)

    print(output)
    return JSONResponse(
        content={"text": output, "yaml": saved_yaml},
        status_code=200
    )


uvicorn.run(app, host="0.0.0.0", port=3032)
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain, SequentialChain, ConversationChain
from langchain.memory import ConversationBufferMemory
import yaml, json

from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

import base64
import requests
import os

from flask import Flask, request, jsonify, Response, abort, make_response
from flask_cors import CORS

load_dotenv()

llm = ChatOpenAI(
    model="o4-mini",
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

SYSTEM_INSTRUCTIONS = """
You are a YAML file generator for writing DB micro-benchmarks.

**Following is the list and description of util functions along with params to be used with each. Use appropriate function according to the use case**
1.  HashedPrimaryStringGen[startNumber, length] - Unique MD5 hash based on an incrementing number and fixed length.
2.  HashedRandomString[min, max, length] - Random MD5 hash from a number in [min, max] with fixed length.
3.  OneNumberFromArray[listOfIntegers] - Random number from a predefined integer list.
4.  OneStringFromArray[listOfStrings] - Random string from a predefined list.
5.  OneUUIDFromArray[listOfUUIDs] - Random UUID from a predefined list.
6.  PrimaryDateGen[totalUniqueDates] - Generates unique dates, one per row.
7.  PrimaryFloatGen[lowerRange, upperRange, decimalPoint] - Unique float between range with fixed decimals.
8.  PrimaryIntGen[lowerRange, upperRange] - Sequential integers between given range.
9.  PrimaryStringGen[startNumber, desiredLength] - Sequential numeric strings starting from a number.
10. PrimaryIntRandomForExecutePhase[lowerRange, upperRange] - Random unique int for execution queries.
11. RandomAString[minLen, maxLen] - Random alphabetic string with length in range.
12. RandomBoolean[] - Random boolean true/false.
13. RandomBytea[minLen, maxLen] - Random hexadecimal string with byte length range.
14. RandomDate[yearLower, yearUpper] - Random date string within year range.
15. RandomInt[min, max] - Random integer between min and max.
16. CyclicSeqIntGen[lowerRange, upperRange] - Repeating int sequence within range.
17. RandomFloat[min, max, decimalPoint] - Random float between range with fixed decimals.
18. RandomJson[fields, valueLength, nestedness] - Random JSON object with control over depth and size.
19. RandomLong[min, max] - Random long integer in range.
20. RandomNoWithDecimalPoints[lower, upper, decimalPlaces] - Random double with fixed decimal precision.
21. RandomNstring[minLen, maxLen] - Random numeric string with length range.
22. RandomNumber[min, max] - Random number (int/float) within range.
23. RandomStringAlphabets[len] - Random alphabetic string of exact length.
24. RandomStringNumeric[len] - Random numeric string of exact length.
25. RandomUUID[] - Random UUID string.
26. RowRandomBoundedInt[low, high] - Random int per row in [low, high].
27. RowRandomBoundedLong[low, high] - Random long per row in [low, high].
28. RandomDateBtwYears[yearLower, yearUpper] - Random date string between two years.
29. RandomPKString[start, end, len] - Random PK-like string in range [start, end] of given length.
30. RandomTextArrayGen[arraySize, minLen, maxLen] - Array of random strings of varied lengths.
31. RandomTimestamp[total] - Unique timestamps generated per row.
32. RandomTimestampWithoutTimeZone[total] - Timestamps without timezone info.
33. RandomTimestampWithTimeZone[total] - Timestamps with timezone info.
34. RandomTimestampWithTimezoneBetweenDates[startDate, endDate] - Timestamps in date range with timezone.
35. RandomTimestampWithTimezoneBtwMonths[startMonth, endMonth] - Timestamps between months of same year (TZ aware).

**Pre-check**: If the input does not describe any database benchmark task, do NOT return a YAML. Respond with a relevant message that mentions to give relevant information.

**Instructions**
1. The user will give you a description in text format. Also use only the util functions provided.
2. Interact with the user when he is stating some workload and ask him for a confirmation to create a yaml giving a summary of the information you have. When he says yes only then generate the YAML.
3. Output **only** a complete YAML document in the exact layout below, **only** after user confirms. Answer any follow up questions related to the yaml.
4. In the template replace the "..." with the appropriate value from the description provided by the user without inverted commas.  
5. Do **not** add commentary or code fences; emit plain YAML only.
6. When ? is used in a query use util in bindings with appropriate function from utils to generate that value.
7. For seperate queries write into different workload in executeRules.
8. **Do not return yaml file if the information provided by the user is irrelevant or incomplete.**
9. If the user description is limited and contain some relevant information, please do the needful to create the yaml with limited information.
10. Keep bindings empty in case where the query in execute Rules doesn't require any parameter.
11. **When the user says to Run or Save or Execute the YAML, you should respond nothing else only "Running your YAML..."**

**YAML template (fill in the appropriate places)**

type: YUGABYTE
driver: com.yugabyte.Driver
url: jdbc:yugabytedb://{{endpoint}}:5433/yugabyte?sslmode=require&ApplicationName=featurebench&reWriteBatchedInserts=true&load-balance=true
username: {{username}}
password: {{password}}
batchsize: 128
isolation: "Extract transaction type from description"
loaderthreads: "Extract loader thread count from description"
terminals: "Extract terminal count from description"
collect_pg_stat_statements: true
yaml_version: v1.0
use_dist_in_explain : true
works:
    work:
        time_secs: "Extract Execution time from description"
        rate: unlimited
        warmup: 60
microbenchmark:
    class: com.oltpbenchmark.benchmarks.featurebench.customworkload.YBDefaultMicroBenchmark
    properties:
        setAutoCommit: true
        create:
            - drop table IF EXISTS 'Extract table name from description';
            - 'write a query to create a table based on user description'

        cleanup:
            - drop table IF EXISTS "Extract table name from description";

        loadRules:
            - table: 'Extract table name from description'
              count: 1
              rows: 'Extract row count from description'
              columns:
                    - name: 'extract column names from the table creation query'
                      count: 1
                      util: 'use appropriate util function. no other function to be used. use only the name of the util. For example to generate a unique date we use PrimaryDateGen function'
                      params: 'use appropriate format for the util function chosen. Example for RandomInt use [1,100000]'

        executeRules:
            - workload: 'give appropriate name of your choice'
              time_secs: 'Extract execution time from description'
              run:
                  - name: 'give appropriate name of your choice'
                    weight: 100
                    queries:
                        - query: 'write an execute query based on user description'
                          bindings:
                            - util: 'use appropriate util function. no other function to be used. use only the name of the util. For example to generate a unique date we use PrimaryDateGen function'
                              params: 'use appropriate format for the util function chosen. Example for RandomInt use [1,100000]'


User has provided the following input : {input}
Conversation so far:{history}
**Utility functions available** (choose from the list the user sees).
"""

yaml_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INSTRUCTIONS)
])

memo=ConversationBufferMemory(k=2)

pipeline = ConversationChain(
    llm=llm,
    prompt=yaml_prompt,
    verbose=True,
    memory=memo
)

chat_pipe=ConversationChain(
    llm=chat_llm,
    prompt=ChatPromptTemplate.from_messages([("system", '''Greetings! You are a small talk handler. Your task is to interact with the user till doesn't skip to main task of yaml generation. Also you need to explain whatever user asks if there is some conversation history. Be formal and remember that you are a part of YAML generator project but don't generate any. Don't distract the conversation from the main goal of YAML generation ad give small but relevant outputs. You are made for user interaction ONLY. Conversation so far:{history}'''),("user", "{history}\nUser: {input}")]),
    verbose=True,
    memory=memo
)


def yaml_upload():
    GITHUB_TOKEN = os.getenv("GITHUB_API_KEY")
    REPO_OWNER = 'yashtyagi-yb'
    REPO_NAME = 'AI_hack'
    BRANCH_NAME = 'main'
    FILE_NAME = 'output.yaml'
    TARGET_PATH = f'AI_gen_workloads/{FILE_NAME}'
    COMMIT_MESSAGE = 'Adding AI generated YAML'

    with open(FILE_NAME, 'rb') as f:
        content = f.read()
        encoded_content = base64.b64encode(content).decode('utf-8')

    url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{TARGET_PATH}'

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

    sha = None
    get_response = requests.get(url + f'?ref={BRANCH_NAME}', headers=headers)

    if get_response.status_code == 200:
        sha = get_response.json().get('sha')

    payload = {
        'message': COMMIT_MESSAGE,
        'content': encoded_content,
        'branch': BRANCH_NAME,
    }

    if sha:
        payload['sha'] = sha

    response = requests.put(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        file_url = response.json()['content']['html_url']
        print('✅ File uploaded successfully!')
        print('🔗 File URL:', file_url)
    else:
        print('❌ Upload failed!')
        print(response.json())


app = Flask(__name__)
CORS(app)
saved_yaml = ''

@app.route("/gen_yaml", methods=["POST"])
def gen_yaml():
    payload = request.get_json(silent=True)
    query_text = payload["query"]

    if not isinstance(query_text, str) or not query_text.strip():
        abort(make_response(jsonify(error="'query' must be a non‑empty string"), 400))

    response = chat_llm.invoke(
        f"Classify the intent of this message: '{query_text}'. Is it 'unimportant information' or 'task'? Only print the answer.")
    if "unimportant information" in response.content:
        yaml_output = chat_pipe.invoke({"input": query_text.strip()})
        print('chat')
    else:
        yaml_output = pipeline.invoke({"input": query_text.strip()})
        response = chat_llm.invoke(
            f"Check whether this output is a YAML file or not. Here's the output : {yaml_output['response']}. Answer **only** either 'Yes' or 'No'")
        print(response.content)
        if response.content == "Yes":
            global saved_yaml
            saved_yaml = yaml_output['response']
        if "Running your YAML..." in yaml_output['response']:
            print("saving yaml...")

            real_yaml = saved_yaml.encode().decode('unicode_escape')
            with open("output.yaml", "w") as f:
                f.write(real_yaml)

            yaml_upload()

        print('task')
    print(yaml_output['response'])
    return Response(yaml_output['response'], mimetype="text/plain", status=200)

app.run(port=3030)
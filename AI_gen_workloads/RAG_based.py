import requests
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.schema import Document
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI


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
with open("all_yamls.txt", "w") as f:
    for group in all_yamls:
        for entry in group:
            for name, yaml_text in entry.items():
                f.write(f"### {name} ###\n")
                f.write(yaml_text + "\n\n")


with open("all_yamls.txt", "r") as f:
    raw_text = f.read()

groups = raw_text.split("### ")
documents = []
for group in groups:
    if not group.strip():
        continue
    parts = group.strip().split("###", 1)
    content = parts[-1].strip()
    documents.append(Document(page_content=content))

embedding_model = OpenAIEmbeddings()
vectorstore = FAISS.from_documents(documents, embedding_model)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
llm = ChatOpenAI(model="gpt-3.5-turbo")
qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)

query = "Create a YAML workload for YugabyteDB that performs index scan on a composite secondary index made on columns name and age"
response = qa_chain.run(query)
print(response)

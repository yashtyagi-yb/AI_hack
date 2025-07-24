import json
import yaml
import requests
from datetime import datetime, timezone
import time

PERFSERVICE_BASE_URL = "http://10.9.0.179:8889"
HEADERS = {'Content-Type': 'application/json'}

UNIVERSE_IP_ADDR = "172.151.53.143"
USERNAME = "yugabyte"
PASSWORD = "Password@321"

test_id = "9275002"
PERFSERVICE_DETAILS_URL = "http://10.9.0.179/dashboard/output/"

data = {
    "comment": "Custom Workload",
    "test_user": "perfgenie",
    "type": "FEATUREBENCH",
    "start_time": (datetime.now(timezone.utc)).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
    "cluster_id": "http://10.9.0.179:8889/clusters/6994002/",
    "payload": {
        "benchbase-repo-branch": "main",
        "client-instance-type": "c5.2xlarge",
        "create": True,
        "load": True,
        "execute": True,
        "cleanup": True,
        "yaml-relative-path": "config/user_workload.yaml",
        "test-user": "perfgenie",
        "config": {
            "username": "yugabyte",
            "password": "Password@321",
            "terminals": 1,
            "load-balance": True
        },
        "existing_client_ip": "172.151.18.89",
        "enable_compaction": False,
        "user_workload": "{}"  # replace with the yaml json received from user
    }
}

gen_yaml_wokload = """
type: YUGABYTE
driver: com.yugabyte.Driver
url: jdbc:yugabytedb://172.151.53.143:5433/yugabyte?sslmode=require&ApplicationName=featurebench&reWriteBatchedInserts=true
username: yugabyte
password: Password@321

batchsize: 128
isolation: TRANSACTION_REPEATABLE_READ
loaderThreads: 1
terminals: 1
collect_pg_stat_statements: true
use_dist_in_explain : true
analyze_on_all_tables: true
yaml_version: v1.0
works:
    work:
        time_secs: 60
        active_terminals: 1
        rate: unlimited
        warmup: 30
microbenchmark:
    class: com.oltpbenchmark.benchmarks.featurebench.customworkload.YBDefaultMicroBenchmark
    properties:
        setAutoCommit: false
        create:
            - DROP TABLE IF EXISTS employees_with_fk_on_pk;
            - create table employees_with_fk_on_pk(id int primary key,name varchar(20) not null, email varchar(100) not null, phone varchar(15), position varchar(10), salary decimal(10,2), project_id int not null);

        cleanup:
            - DROP TABLE IF EXISTS employees_with_fk_on_pk;

        loadRules:
            - table: employees_with_fk_on_pk
              rows: 1000000
              columns:
                  - name: id
                    util: PrimaryIntGen
                    params: [1, 1000000]
                  - name: name
                    util: RandomAString
                    params: [1, 20]
                  - name: email
                    util: RandomAString
                    params: [1, 100]
                  - name: phone
                    util: RandomNstring
                    params: [10, 15]
                  - name: position
                    util: RandomAString
                    params: [1, 10]
                  - name: salary
                    util: RandomNoWithDecimalPoints
                    params: [1, 1000000, 2]
                  - name: project_id
                    util: RandomInt
                    params: [1,100000]

        executeRules:
            - workload: FK_G1_1_fk-on-pk_insert
              run:
                  - name: FK_G1_1_fk-on-pk_insert
                    weight: 100
                    queries:
                        - query: insert into employees_with_fk_on_pk values(?,?,?,?,?,?,?);
                          bindings:
                              - util: PrimaryIntGen
                                params: [1000001, 9000000]
                              - util: RandomAString
                                params: [1, 20]
                              - util: RandomAString
                                params: [1, 100]
                              - util: RandomNstring
                                params: [10, 15]
                              - util: RandomAString
                                params: [1, 10]
                              - util: RandomNoWithDecimalPoints
                                params: [1, 1000000, 2]
                              - util: RandomInt
                                params: [1,100000]
"""

# after confirmation, execute the yaml of perfservice
def run_test(gen_yaml_workload):
    yaml_data = yaml.safe_load(gen_yaml_workload)
    data['payload']['user_workload'] = yaml_data
    json_data = json.dumps(data)
    url = "{}/tests/".format(PERFSERVICE_BASE_URL)
    resp = requests.post(url=url, data=json_data, headers=HEADERS, verify=False)
    resp_json = resp.json()
    return resp_json['test_id']

# based on the test status, we can print the message whether test is running or completed
def get_test_status(test_id):
    url = "{}/tests/{}/".format(PERFSERVICE_BASE_URL, test_id)
    print("Getting status for test_id : ", test_id)
    resp = requests.get(url=url, headers=HEADERS)
    if resp.status_code in [200, 201]:
        response = resp.json()
        test_status = response["status"]
        if test_status == "COMPLETED":
            return True, "Test has COMPLETED"  # get_test_report(test_id)""
        elif test_status == "JENKINS_JOB_FAILED":
            return False, "Test has FAILED, please check for logs"
        elif test_status == "RUNNING":
            return False, f"Your test is RUNNING.. Details can be found at {PERFSERVICE_DETAILS_URL}{test_id} "
        else:
            return False, f"Unknown Status {test_status}"

# when the test is completed get the report URL
# def get_test_report(test_id):
#    return report_url

def main():
 #   test_id = run_test(gen_yaml_wokload)
    status, msg = get_test_status(test_id)
    print(msg)


if __name__ == "__main__":
    main()

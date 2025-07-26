import json
import time

import yaml
import requests
from datetime import datetime, timezone
import base64
import configparser

config_prop = configparser.ConfigParser()
config_prop.read('config.properties')

class PerfServiceClient:
    def __init__(self,
                 endpoint,
                 username,
                 password,
                 client_ip_addr,
                 db_provider):
        self.dashboard_url = config_prop['DEFAULT']['dashboard_url']
        self.base_url = self.dashboard_url + ":8889"
        self.headers = {'Content-Type': 'application/json'}
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.db_provider = db_provider
        self.cluster_id = config_prop['YB']['cluster_id']
        self.client_ip_addr = client_ip_addr

    def _build_payload(self):
        return {
            "comment": "Custom Workload",
            "db_provider": self.db_provider,
            "test_user": "perfgenie",
            "type": "FEATUREBENCH",
            "start_time": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            "cluster_id": f"{self.base_url}/clusters/{self.cluster_id}/",
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
                    "username": self.username,
                    "password": self.password,
                    "endpoint": self.endpoint,
                    "terminals": 1,
                    "load-balance": True
                },
                "existing_client_ip": self.client_ip_addr,
                "enable_compaction": False,
                "user_workload": "{}"
            }
        }

    def run_test(self, gen_yaml_workload):
        gen_yaml_workload = gen_yaml_workload.replace("{{endpoint}}", self.endpoint)
        gen_yaml_workload = gen_yaml_workload.replace("{{username}}", self.username)
        gen_yaml_workload = gen_yaml_workload.replace("{{password}}", self.password)

        yaml_data = yaml.safe_load(gen_yaml_workload)
        payload = self._build_payload()
        payload['payload']['user_workload'] = yaml_data
        payload['region'] = config_prop[self.db_provider]['region']
        payload['subnet_id'] = config_prop[self.db_provider]['subnet_id']
        payload['az'] = config_prop[self.db_provider]['az']
        payload['security_group'] = config_prop[self.db_provider]['security_group']
        json_data = json.dumps(payload)
        print(payload)
        url = f"{self.base_url}/tests/"
        resp = requests.post(url=url, data=json_data, headers=self.headers, verify=False)

        if resp.status_code not in [200, 201]:
            raise Exception(f"Test creation failed: {resp.text}")
        test_id = resp.json().get("test_id")
        status,msg=self.get_test_status(test_id)
        return test_id,msg

    # check status for all test_ids, return results appropriately
    def get_test_status(self, *test_ids):
        return_str = ""
        all_completed = True
        for test_id in test_ids:
            url = f"{self.base_url}/tests/{test_id}/"
            resp = requests.get(url=url, headers=self.headers)
            if resp.status_code in [200, 201]:
                response = resp.json()
                test_status = response["status"]
                if test_status == "COMPLETED":
                    return_str = return_str + f"\n✅ Test {test_id} COMPLETED. Report: {self.get_test_report(test_id, do_status_check=False)}"
                elif test_status == "JENKINS_JOB_FAILED":
                    return_str = return_str + f"\n❌ Test {test_id} FAILED. Logs: {self.dashboard_url}/dashboard/output/{test_id}"
                    all_completed=False
                elif test_status == "RUNNING":
                    return_str = return_str + f"\n⏳ Test {test_id} is RUNNING. Details: {self.dashboard_url}/dashboard/output/{test_id}"
                    all_completed=False
                elif test_status == "QUEUED":
                    return_str = return_str + f"\n🕒 Test {test_id} is QUEUED. Details: {self.dashboard_url}/dashboard/output/{test_id}"
                    all_completed=False
                else:
                    return_str = return_str + f"\n❓ Unknown status '{test_status}' for test {test_id}"
                    all_completed=False
            else:
                return_str = return_str + f"\n⚠️ Failed to fetch status for test {test_id} (HTTP {resp.status_code}"
                all_completed=False
        if all_completed:
            return_str = f"\nComparison Report : {self.get_test_report(test_ids, do_status_check=False)}"
        return all_completed,return_str

    def get_test_report(self, *test_ids, do_status_check=True):
        if do_status_check:
            status,msg = self.get_test_status(*test_ids)
            if not status:
                return "Not all tests have completed. " + msg
        test_id_data = [
            {
                "name": test_id,
                "isBaseline": True,
                "test_id": test_id
            }
            for test_id in test_ids
        ]
        test_id_json = json.dumps(test_id_data)
        encoded = base64.b64encode(test_id_json.encode()).decode()
        return f"{self.dashboard_url}/report/view/{encoded}"

def main():
    client_yb = PerfServiceClient(config_prop['YB']['endpoint'], config_prop['YB']['username'], config_prop['YB']['password'],
                                  config_prop['YB']['client_ip_addr'], config_prop['YB']['provider'])
    client_pg = PerfServiceClient(config_prop['PG']['endpoint'], config_prop['PG']['username'], config_prop['PG']['password'],
                                  config_prop['PG']['client_ip_addr'], config_prop['PG']['provider'])
    # Example usage:
    # test_id1 = client_yb.run_test(yb_yaml.yb_yaml)
    # test_id2 = client_pg.run_test(pg_yaml.pg_yaml)
    # time.sleep(300)
    # status, message = client_yb.get_test_status(test_id1,test_id2)
    # print(message)

if __name__ == "__main__":
    main()


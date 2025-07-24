import json
import yaml
import requests
from datetime import datetime, timezone
import base64

class PerfServiceClient:
    def __init__(self,
                 dashboard_url="http://10.9.0.179",
                 universe_ip="172.151.53.143",
                 username="yugabyte",
                 password="Password@321"):
        self.base_url = dashboard_url + ":8889"
        self.headers = {'Content-Type': 'application/json'}
        self.universe_ip = universe_ip
        self.username = username
        self.password = password
        self.dashboard_url = dashboard_url
        self.cluster_id = "6994002"

    def _build_payload(self):
        return {
            "comment": "Custom Workload",
            "test_user": "perfgenie",
            "type": "FEATUREBENCH",
            "start_time": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            "cluster_id": f"{self.base_url}/clusters/6994002/",
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
                    "endpoint": self.universe_ip,
                    "terminals": 1,
                    "load-balance": True
                },
                "existing_client_ip": "172.151.18.89",
                "enable_compaction": False,
                "user_workload": "{}"
            }
        }

    def run_test(self, gen_yaml_workload):
        gen_yaml_workload = gen_yaml_workload.replace("{{endpoint}}", self.universe_ip)
        gen_yaml_workload = gen_yaml_workload.replace("{{username}}", self.username)
        gen_yaml_workload = gen_yaml_workload.replace("{{password}}", self.password)

        yaml_data = yaml.safe_load(gen_yaml_workload)
        payload = self._build_payload()
        payload['payload']['user_workload'] = yaml_data

        json_data = json.dumps(payload)
        url = f"{self.base_url}/tests/"
        print(url)
        resp = requests.post(url=url, data=json_data, headers=self.headers, verify=False)

        if resp.status_code not in [200, 201]:
            raise Exception(f"Test creation failed: {resp.text}")

        return resp.json().get("test_id")

    def get_test_status(self, test_id):
        url = f"{self.base_url}/tests/{test_id}/"
        print("Getting status for test_id:", test_id)
        resp = requests.get(url=url, headers=self.headers)

        if resp.status_code in [200, 201]:
            response = resp.json()
            test_status = response["status"]
            if test_status == "COMPLETED":
                return True, f"Test has COMPLETED. Click for report {self.get_test_report(test_id)}"
            elif test_status == "JENKINS_JOB_FAILED":
                return False, "Test has FAILED, please check for logs"
            elif test_status == "RUNNING":
                return False, f"Your test is RUNNING.. Details can be found at {self.dashboard_url}/dashboard/output/{test_id}"
            elif test_status == "QUEUED":
                return False, f"Your test will start soon. Details can be found at {self.dashboard_url}/dashboard/output/{test_id}"
            else:
                return False, f"Unknown Status: {test_status}"
        else:
            return False, f"Failed to get test status: {resp.status_code}"

    def get_test_report(self, test_id):
        test_id_data = [{
            "name": test_id,
            "isBaseline": True,
            "test_id": test_id
        }]
        test_id_json = json.dumps(test_id_data)
        encoded = base64.b64encode(test_id_json.encode()).decode()
        return f"{self.dashboard_url}/report/view/{encoded}"


def main():
    client = PerfServiceClient()
    # Example usage:
    # test_id = client.run_test(client.user_yaml_string)
    # status, message = client.get_test_status(test_id)
    # message = client.get_test_report("9275202")
    # print(message)

if __name__ == "__main__":
    main()


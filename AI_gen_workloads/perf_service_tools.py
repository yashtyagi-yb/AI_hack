from langchain_core.tools import tool
from perf_service_util import PerfServiceClient
import configparser

config = configparser.ConfigParser()
config.read('config.properties')
_perf_client = {"YB": PerfServiceClient(config['YB']['endpoint'], config['YB']['username'], config['YB']['password'],config['YB']['client_ip_addr'],config['YB']['provider']),
                "PG": PerfServiceClient(config['PG']['endpoint'], config['PG']['username'], config['PG']['password'],config['PG']['client_ip_addr'],config['PG']['provider'])}

@tool
def run_test_tool(yaml_string: str) -> str:
    """
    This tool helps agent to execute the test. You will receive a YAML in string formart which you should use to run the test.

    Args:
        yaml_string: YAML file in string format

    Returns:
       Test id in format: Your test has started. Here are the test details: <test link>. Also instruct the user to comeback in sometime to check the status of the test.
    """
    try:
        if "POSTGRES" in yaml_string:
            test_id = _perf_client["PG"].run_test(yaml_string)
            return f"Test started successfully. Test ID: {test_id}"
        else:
            test_id = _perf_client["YB"].run_test(yaml_string)
            return f"Test started successfully. Test ID: {test_id}"

    except Exception as e:
        return f"Error running test: {str(e)}"


@tool
def get_test_status_tool(test_id: str) -> str:
    """
    This tool lets you get/check the status of a test. When you receive this request, fetch the status of all the tests id.
    Returns status and report URL if completed.
    **Return the output as returned by the function as is**
    """

    try:
        message = _perf_client['YB'].get_test_status(test_id)
        return message
    except Exception as e:
        return f"Error retrieving test status: {str(e)}"


@tool
def get_test_report_tool(test_id: str) -> str:
    """
    For the completed test the agent can call this tool to get the test report.
    If two test ids are passed then a comparison report can be shared by passing both test ids to the tool.
    Returns the report and the message to the user as returned by the tool.
    Make the report link clickable
    """
    try:
        message = _perf_client['YB'].get_test_report(*test_id)
        return message
    except Exception as e:
        return f"Error retrieving test status: {str(e)}"

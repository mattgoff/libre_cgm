import json
import numpy as np
import os
import requests
from dotenv import load_dotenv
from scipy.stats import linregress


class LibreDataHandler:
    load_dotenv()
    MGID = os.getenv("MGID")
    SGID = os.getenv("SGID")
    DESTINATION = os.getenv("DESTINATION")
    BASE_URL = 'https://api-us.libreview.io/'
    URLs = {
        "login": BASE_URL + 'llu/auth/login',
        "tou": BASE_URL + 'auth/continue/tou',
        "account": BASE_URL + 'account',
        "graph": BASE_URL + 'llu/connections/{USERID}/graph',
        "logbook": BASE_URL + 'llu/connections/{USERID}/logbook',
        "connections": BASE_URL + 'llu/connections'
    }

    def __init__(self):
        self.session = requests.Session()
        self.glucose_data = dict()
        self.bearer_token = None
        self.account_info = None
        self.libre_connections = None
        self.logbook = None
        self.tou_response = None
        self.auth_data = self._load_credentials()
        self.headers = self._build_headers
        auth_response = self._post(self.URLs['login'], data=self.auth_data)
        self.add_bearer_token_to_headers(auth_response['data']['authTicket']['token'])

    def __enter__(self):
        """
        Method called when entering a 'with' statement.

        :return: The object itself.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        :param exc_type: The type of the exception that was raised, if any.
        :param exc_val: The exception object that was raised, if any.
        :param exc_tb: The traceback object associated with the exception, if any.
        :return: None
        """
        self.session.close()
        print("Closing up http session")

    @staticmethod
    def _load_credentials():
        """
        Load the credentials from environment variables.

        :return: The credentials as a JSON string.
        """
        return json.dumps(
            {
                "email": os.getenv('email'),
                "password": os.getenv('password')
            }
        )

    @property
    def _build_headers(self):
        """
        Returns the headers dictionary used for HTTP requests.

        :return: A dictionary containing the headers for the HTTP requests.
        :rtype: dict
        """
        return {
            'version': '4.7',
            'product': 'llu.ios',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def add_bearer_token_to_headers(self, token):
        """
        Adds a bearer token to the headers.

        :param token: The bearer token to add.
        :return: None
        """
        self.headers['Authorization'] = f"Bearer {token}"

    def _post(self, url, data=None):
        """
        Sends a POST request to the given URL with optional data.

        :param url: The URL to send the POST request to.
        :param data: Optional data to be sent with the POST request.
        :return: The JSON response from the POST request.
        """
        print()
        response = self.session.post(url, headers=self.headers, data=data)
        response.raise_for_status()
        return response.json()

    def _get(self, url):
        """
            Send HTTP GET request to the specified URL and return the response as a JSON object.

            :param url: The URL to send the GET request to.
            :return: The response as a JSON object.
        """
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _calculate_trend(self):
        """:return: The trend of the glucose data.

            The trend is calculated by fitting a linear regression line to the last 10 glucose data points.
            If the slope of the line is positive, the trend is classified as "up".
            If the slope of the line is negative, the trend is classified as "down".
            If the slope of the line is zero, the trend is classified as "steady".
        """
        graph_data = self.glucose_data['data']['graphData']
        series = graph_data[-10::] if len(graph_data) > 9 else graph_data
        trend = [x['Value'] for x in series]
        slope, _, _, _, _ = linregress(np.arange(len(trend)), trend)
        return "up" if slope > 0 else "down" if slope < 0 else "steady"

    def accept_tou(self):
        """
        Accepts the terms of use and updates the self.tou_response attribute.

        :return: None
        """
        self.tou_response = self._post(self.URLs['tou'])

    def get_account(self):
        """
        Return the account information.

        :return: The account information.
        """
        self.account_info = self._get(self.URLs['account'])

    def get_graph(self, account):
        """
        Retrieves the glucose data graph for the specified account.

        :param account: The account for which to retrieve the graph.
        :type account: str
        :return: None
        :rtype: None
        """
        self.glucose_data = self._get(self.URLs['graph'].format(USERID=account))

    def get_connections(self):
        """
        Retrieve connections from the specified URL.

        :return: None
        """
        self.libre_connections = self._get(self.URLs['connections'])

    def get_logbook(self, account):
        """
        :param account: The account identifier for which the logbook is requested.
        :return: None

        """
        self.logbook = self._get(self.URLs['logbook'].format(USERID=account))

    @staticmethod
    def print_glucose(data):
        """
        Prints the glucose data.

        :param data: Dictionary containing the glucose data.
                     Example: {
                         'time': '2021-10-15 08:30',
                         'value': 120,
                         'trend': 'stable'
                     }
        :type data: dict
        :return: None
        """
        print(f"{data['time']}\tValue: {data['value']}\tTrend: {data['trend']}")

    def send_glucose_data(self):
        """
        Sends glucose data to a destination via a POST request.

        :return: None
        """
        glucose_item = self.glucose_data['data']['connection']['glucoseItem']
        glucose_item['Trend'] = self._calculate_trend()
        data = {
            'time': glucose_item['Timestamp'],
            'value': glucose_item['Value'],
            'trend': glucose_item['Trend']
        }
        self.print_glucose(data)
        response = requests.post(self.DESTINATION, data=json.dumps(data))
        response.raise_for_status()


if __name__ == "__main__":
    with LibreDataHandler() as libre:
        libre.get_graph(libre.SGID)
        libre.send_glucose_data()

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
        self.auth_data = self._load_credentials
        self.headers = self._build_headers
        auth_response = self._post(self.URLs['login'], data=self.auth_data)
        self.add_bearer_token_to_headers(auth_response['data']['authTicket']['token'])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
        print("Closing up http session")

    @property
    def _load_credentials(self):
        return json.dumps(
            {
                "email": os.getenv('email'),
                "password": os.getenv('password')
            }
        )

    @property
    def _build_headers(self):
        return {
            'version': '4.7',
            'product': 'llu.ios',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def add_bearer_token_to_headers(self, token):
        self.headers['Authorization'] = f"Bearer {token}"

    def _post(self, url, data=None):
        response = self.session.post(url, headers=self.headers, data=data)
        response.raise_for_status()
        return response.json()

    def _get(self, url):
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _calculate_trend(self):
        graph_data = self.glucose_data['data']['graphData']
        series = graph_data[-10::] if len(graph_data) > 9 else graph_data
        trend = [x['Value'] for x in series]
        slope, _, _, _, _ = linregress(np.arange(len(trend)), trend)
        return "up" if slope > 0 else "down" if slope < 0 else "steady"

    def accept_tou(self):
        self.tou_response = self._post(self.URLs['tou'])

    def get_account(self):
        self.account_info = self._get(self.URLs['account'])

    def get_graph(self, account):
        self.glucose_data = self._get(self.URLs['graph'].format(USERID=account))

    def get_connections(self):
        self.libre_connections = self._get(self.URLs['connections'])

    def get_logbook(self, account):
        self.logbook = self._get(self.URLs['logbook'].format(USERID=account))

    @staticmethod
    def print_glucose(data):
        print(f"{data['time']}\tValue: {data['value']}\tTrend: {data['trend']}")

    def send_glucose_data(self):
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

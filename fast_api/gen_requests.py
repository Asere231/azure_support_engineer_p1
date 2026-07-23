import subprocess
import os
import re
import json
import time
import random
import requests

def get_token():
    jwt_url = 'http://20.200.188.8:8080'

    user_data = {
        'username': 'Traffic Gen Tester',
        'password': 'SOMEPASSWORD'
    }

    # Attempt to register, even if we already did.
    response = requests.post(url=f'{jwt_url}/register', json=user_data)

    # Login.
    response = requests.post(url=f'{jwt_url}/login', json=user_data)
    response_data = response.json()

    if 'access_token' in response_data:
        print(f'Requested new token, got {response_data['access_token']}')
        return f"Bearer {response_data['access_token']}"

    raise Exception('FAILED TO GET ACCESS TOKEN')

def print_status(total, failed):
    print(f'TOTAL: {total} - FAILED: {failed} - ({failed/total})')
    

def main():
    start_time          = time.perf_counter()
    duration            = 600
    checkpoint_duration = 5
    next_checkpoint     = start_time + checkpoint_duration

    total_sent      = 1
    failed_requests = 0

    try:
        request_headers = {
            'Authorization': get_token(),
            'Content-Type':	'application/json; charset=utf-8'
        }
        status_data = {
            "name": "Microsoft",
            "url": "https://www.microsoft.com/"
        }

        while time.perf_counter() - start_time < duration: 
            request_wait_time = random.uniform(0.0, 0.1)
            #time.sleep(request_wait_time)

            response = requests.post(url='https://api-management-microservices.azure-api.net/api/status-code', 
                        headers=request_headers, json=status_data)
            response_data = response.json()

            if 'error' in response_data:
                request_headers['Authorization'] = get_token()
                failed_requests += 1

            total_sent += 1

            if time.perf_counter() > next_checkpoint:
                next_checkpoint += checkpoint_duration
                print_status(total_sent, failed_requests)
    finally:
        print(f'DONE')
        print_status(total_sent, failed_requests)

main()
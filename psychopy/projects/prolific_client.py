#!/usr/bin/env python
# -*- coding: utf-8 -*-
from decimal import Decimal

import requests

api_url = "https://test.prolific.co/api/v1"
client_url = "https://test-client.prolific.co"


class ProlificClient:

    def __init__(self, token):
        self.token = token

    def with_token(self, data):
        return {**{"token": self.token}, **data}

    def retrieve_prolific_user(self):
        response = requests.get(f"{api_url}/users/me/", headers={"authorization": f"Bearer {self.token}"})

        if response.status_code != 200:
            return None

        return self.with_token(response.json())

    def calculate_total(self, participants, reward):
        response = requests.post(f"{api_url}/study-cost-calculator/", headers={"authorization": f"Bearer {self.token}"},
                                 json={
                                          "reward": int(reward*100),
                                          "total_available_places": participants,
                                          "study_type": "SINGLE"
                                        }
                                 )

        if response.status_code != 200:
            return None

        return Decimal(response.json()["total_cost"]) / 100

    def create_study(self, title, internal_name, description, external_study_url, code, participants, duration, reward):
        """
        Returns
        -------
        data to create a prolific project
        """
        projDict = {}
        projDict['name'] = title
        projDict['internal_name'] = internal_name
        projDict['description'] = description
        projDict['external_study_url'] = external_study_url
        projDict['completion_code'] = code
        projDict['callback_url'] = f"https://test-client.prolific.co/submissions/complete?cc={code}"
        projDict['total_available_places'] = participants
        projDict['estimated_completion_time'] = duration
        projDict['maximum_allowed_time'] = 13
        projDict['reward'] = int(reward*100)
        projDict['prolific_id_option'] = 'url_parameters'
        projDict['completion_option'] = 'url'
        projDict['device_compatibility'] = [
                "mobile",
                "desktop",
                "tablet"
            ]
        projDict['peripheral_requirements'] = []
        projDict['custom_screening_checked'] = False
        projDict['publish_at'] = None
        projDict['study_type'] = "SINGLE"
        projDict['eligibility_requirements'] = []

        response = requests.post(f"{api_url}/studies/", headers={"authorization": f"Bearer {self.token}"},
                                 json=projDict
                                 )

        if response.status_code != 201:
            return None

        study = response.json()
        extra = {"url": f"{client_url}/studies/{study['id']}/"}
        return {**study, **extra}


    def publish_study(self, id):
        """
        Returns
        -------
        data to update a prolific project
        """


        response = requests.post(f"{api_url}/studies/{id}/transition/", headers={"authorization": f"Bearer {self.token}"},
                                 json={
                                          "action": "PUBLISH"
                                        }

                                 )

        if response.status_code != 200:
            return None

        return response.json()

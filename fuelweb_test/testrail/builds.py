#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import unicode_literals

import re

import requests
from requests.packages.urllib3 import disable_warnings

from fuelweb_test.testrail.settings import JENKINS
from fuelweb_test.testrail.settings import logger


disable_warnings()


def get_jobs_for_view(view):
    """Return list of jobs from specified view
    """
    view_url = "/".join([JENKINS["url"], 'view', view, 'api/json'])
    logger.debug("Request view data from {}".format(view_url))
    view_data = requests.get(view_url).json()
    jobs = [job["name"] for job in view_data["jobs"]]
    return jobs


def get_downstream_builds_from_html(url):
    """Return list of downstream jobs builds from specified job
    """
    url = "/".join([url, 'downstreambuildview/'])
    logger.debug("Request downstream builds data from {}".format(url))
    response = requests.get(url).text
    jobs = []
    raw_downstream_builds = re.findall(
        '.*downstream-buildview.*href="(/job/\S+/[0-9]+/).*', response)
    for raw_build in raw_downstream_builds:
        sub_job_name = raw_build.split('/')[2]
        sub_job_build = raw_build.split('/')[3]
        build = Build(name=sub_job_name, number=sub_job_build)
        jobs.append(
            {
                'name': build.name,
                'number': build.number,
                'result': build.build_data['result']
            }
        )

    return jobs


def get_build_artifact(url, artifact):
    """Return content of job build artifact
    """
    url = "/".join([url, 'artifact', artifact])
    logger.debug("Request artifact content from {}".format(url))
    return requests.get(url).text


class Build(object):
    def __init__(self, name, number):
        """Get build info via Jenkins API, get test info via direct HTTP
        request.

        If number is 'latest', get latest completed build.
        """

        self.name = name

        if number == 'latest':
            job_info = self.get_job_info(depth=0)
            self.number = job_info["lastCompletedBuild"]["number"]
        elif number == 'latest_started':
            job_info = self.get_job_info(depth=0)
            self.number = job_info["lastBuild"]["number"]
        else:
            self.number = int(number)

        self.build_data = self.get_build_data(depth=0)
        self.url = self.build_data["url"]

    def get_job_info(self, depth=1):
        job_url = "/".join([JENKINS["url"], 'job', self.name,
                            'api/json?depth={depth}'.format(depth=depth)])
        logger.debug("Request job info from {}".format(job_url))
        return requests.get(job_url).json()

    def get_job_console(self):
        job_url = "/".join([JENKINS["url"], 'job', self.name,
                            str(self.number), 'consoleText'])
        logger.debug("Request job console from {}".format(job_url))
        return requests.get(job_url).text

    def get_build_data(self, depth=1):
        build_url = "/".join([JENKINS["url"], 'job',
                              self.name,
                              str(self.number),
                              'api/json?depth={depth}'.format(depth=depth)])
        logger.debug("Request build data from {}".format(build_url))
        return requests.get(build_url).json()

    @staticmethod
    def get_test_data(url, result_path=None):
        if result_path:
            test_url = "/".join(
                [url.rstrip("/"), 'testReport'] + result_path + ['api/json'])
        else:
            test_url = "/".join([url.rstrip("/"), 'testReport', 'api/json'])

        logger.debug("Request test data from {}".format(test_url))
        return requests.get(test_url).json()

    def test_data(self, result_path=None):
        try:
            data = self.get_test_data(self.url, result_path)
        except Exception as e:
            logger.warning("No test data for {0}: {1}".format(
                self.url,
                e,
            ))
            # If we failed to get any tests for the build, return
            # meta test case 'jenkins' with status 'failed'.
            data = {
                "suites": [
                    {
                        "cases": [
                            {
                                "name": "jenkins",
                                "className": "jenkins",
                                "status": "failed",
                                "duration": 0
                            }
                        ]
                    }
                ]
            }

        return data

    def __str__(self):
        string = "\n".join([
            "{0}: {1}".format(*item) for item in self.build_record()
        ])
        return string

    def build_record(self):
        """Return list of pairs.

        We cannot use dictionary, because columns are ordered.
        """

        data = [
            ('number', str(self.number)),
            ('id', self.build_data["id"]),
            ('description', self.build_data["description"]),
            ('url', self.build_data["url"]),
        ]

        test_data = self.test_data()
        for suite in test_data['suites']:
            for case in suite['cases']:
                column_id = case['className'].lower().replace("_", "-")
                data.append((column_id, case['status'].lower()))

        return data

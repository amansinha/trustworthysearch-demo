# -*- coding: utf-8 -*-
'''
Copyright (c) 2020, Trustworthy AI, Inc. All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1.  Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2.  Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

3.  Neither the name of the copyright holder(s) nor the names of any contributors
may be used to endorse or promote products derived from this software without
specific prior written permission. No license is granted to the trademarks of
the copyright holders even if such marks are included in this software.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''
###############################################################################
# job_killer.py
# Author: Aman Sinha
# Purpose: Kill a job using its specified job id.
# python job_killer.py --jobid 7922
# Notes:
#   to make sure my editor saves in utf-8 here is a nice character: é
#   The jobid is printed by the broker upon job start.
###############################################################################
import argparse
import grpc

import trustworthy_search_pb2_grpc as rpc
import trustworthy_search_pb2 as ts


# Main function to run a job
def run(SSLcertfile, serverURL, serverport, jobid):
    # open client to search server
    # The communication is authenticated via SSL for security
    with open(SSLcertfile, 'rb') as f:
        creds = grpc.ssl_channel_credentials(f.read())
    search_channel = grpc.secure_channel(serverURL+':'+str(serverport), creds)
    search_stub = rpc.TrustworthySearchStub(search_channel)
    search_stub.KillJob(ts.Job(jobid=jobid))
    search_channel.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--SSLcert', default='trial_server.crt', help='default = trial_server.crt')
    parser.add_argument('--serverURL', default='trial.trustworthy.ai', help='default = trial.trustworthy.ai')
    parser.add_argument('--serverport', type=int, default=443, help='default = 443')
    parser.add_argument('--jobid', type=int, help='no default value', required=True)
    args = parser.parse_args()
    run(args.SSLcert, args.serverURL, args.serverport, args.jobid)

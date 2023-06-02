from jira import JIRA
import datetime
import matplotlib as plt
from progress.bar import Bar
from fedex import Fedex
from pyzipcode import ZipCodeDatabase

class IC:
    def __init__(self, auth_username, password, ic_username):
        self.jira = JIRA('https://jira.yelpcorp.com', auth=(auth_username, password))
        self.fedex = Fedex()
        self.zipDB = ZipCodeDatabase()
        self.username = ic_username
        self.components = self.jira.project_components("HELPDESK")
        self.ic_component_metrics = {}

    def component_metrics(self, offset=30):
        """Grab IC Component metrics from HELPDESK Project"""

        with Bar('Getting IC Component Metrics..', max=len(self.components)) as bar:
            for component in self.components:
                maxResults = 50
                jql = f'project = HELPDESK AND resolutiondate >= -{offset}d AND assignee = {self.username} AND component in ("{component.name}")'
                issues = self.jira.search_issues(jql, maxResults=maxResults)
                print(component.name)
                while(len(issues) >= maxResults):
                    maxResults += 50
                    issues = self.jira.search_issues(jql, maxResults=maxResults)

                if component.name == 'Fedex' and len(issues):
                    self.ic_component_metrics[component.name] = {'total_issues':len(issues), 'carriers': {'GROUND_HOME_DELIVERY': 0, 'FIRST_OVERNIGHT': 0,\
                                                                'PRIORITY_OVERNIGHT': 0, 'STANDARD_OVERNIGHT': 0,'FEDEX_2_DAY': 0,'FEDEX_2_DAY_AM': 0, 'FEDEX_EXPRESS_SAVER': 0,\
                                                                'INTERNATIONAL_ECONOMY': 0, 'FEDEX_GROUND': 0},'time': 0, 'inbound_len': 0,'outbound_len': 0,'cost_avg': 0, 'logi_costs_total': 0}
                    num_shipments = 0
                    for issue in issues:
                        tracking_nums = [issue.fields.customfield_16736, issue.fields.customfield_16737]    #inbound @[0] outbound @[1]
                        tracking_nums = [tracking_nums.remove(x) for x in tracking_nums if x == None]       #remove indicies that werent found in issue
                        num_shipments += len(tracking_nums)
                        tracking_results = [(self.fedex.track_shipment(x, return_raw=True)) for x in tracking_nums]
                        tracking_nums = [tracking_nums.remove(x) for x in tracking_nums if x == None] 
                        tracking_results = [x['output']['completeTrackResults'][0]['trackResults'][0] for x in tracking_results if x != None]
                    
                        for shipment in tracking_results:
                            carrier_code = shipment['serviceDetail']['type']
                            self.ic_component_metrics[component.name]['carriers'][carrier_code]+= 1
                            sender_zipCode = self.zipDB.find_zip(city=shipment['shipperInformation']['address']['city'].lower(),\
                                                                state=shipment['shipperInformation']['address']['stateOrProvinceCode'])[0].zip
                            recipient_zipCode = self.zipDB.find_zip(city=shipment['recipientInformation']['address']['city'].lower(),\
                                                                    state=shipment['recipientInformation']['address']['stateOrProvinceCode'])[0].zip
                            if carrier_code == 'GROUND_HOME_DELIVERY':
                                carrier_code = 'FEDEX_GROUND'           #FDX cost est. api lumps all ground services under FEDEX_GROUND
                            cost = float(self.fedex.estimate(sender_zipCode, recipient_zipCode, 10, 1000, carrier_code)['totalNetCharge'])
                            self.ic_component_metrics[component.name]['logi_costs_total'] += cost

                            date_created = issue.fields.created[0:-5]
                            date_resolved = issue.fields.resolutiondate[0:-5]
                            date_delta = (datetime.datetime.strptime(date_resolved, '%Y-%m-%dT%H:%M:%S.%f') - datetime.datetime.strptime(date_created, '%Y-%m-%dT%H:%M:%S.%f')).total_seconds()
                            self.ic_component_metrics[component.name]['time'] += date_delta

                        try:
                            self.ic_component_metrics[component.name]['cost_avg'] = self.ic_component_metrics[component.name]['logi_costs_total'] / len(issues) / 86400
                        except ZeroDivisionError:
                            pass
                elif len(issues):
                    self.ic_component_metrics[component.name] = {'total_issues': len(issues), 'time': 0, 'priorities': 
                                                                {"P3 - We'll Get It Done": 0, "P2 - The Sooner The Better": 0, 
                                                                "P1 - We're On It": 0, "P4 - Let's Set A Date": 0, "P4 - Hella Crucial": 0}}
                    for issue in issues:
                        date_created = issue.fields.created[0:-5]
                        date_resolved = issue.fields.resolutiondate[0:-5]
                        date_delta = (datetime.datetime.strptime(date_resolved, '%Y-%m-%dT%H:%M:%S.%f') - datetime.datetime.strptime(date_created, '%Y-%m-%dT%H:%M:%S.%f')).total_seconds()
                        self.ic_component_metrics[component.name]['time'] += date_delta
                        self.ic_component_metrics[component.name]['priorities'][issue.fields.priority.name] += 1
                bar.next()
                
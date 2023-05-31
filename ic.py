from jira import JIRA
from datetime import datetime
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

    def fdx_ic_metrics(self, offset=30):
        """Search Jira for IC tickets with Fedex, Fedex Shipping, or Fedex Pickup Component"""
        
        fdx_issues = self.jira.search_issues(f'project = HELPDESK AND status in (Resolved, Closed) AND assignee = {self.username} AND \
                                            resolutiondate >= -{offset}d and component in(Fedex, "Fedex Shipping", "Fedex Pickup")')
        
        for i in fdx_issues:
            if i.fields.customfield_16736 != None:
                self.ib_tracking_nums.append(i.fields.customfield_16736)
            if i.fields.customfield_16737 != None:
                self.ob_tracking_nums.append(i.fields.customfield_16737)

    def component_metrics(self, offset=30):
        """Grab IC Component metrics from HELPDESK Project"""
        
        with Bar('Getting IC Component Metrics..', max=len(self.components)) as bar:
            for i in self.components:
                issues = self.jira.search_issues(f'project = HELPDESK AND status in (Resolved, Closed) AND assignee = {self.username} AND \
                                                resolutiondate >= -{offset}d and component in("{i.name}")')
                if i.name == 'Fedex' and len(issues):
                    self.ic_component_metrics[i.name] = {'total_issues':len(issues), 'time': 0, 'inbound_len': 0, 'outbound_len': 0, 'cost_avg': 0}
                    for x in issues:
                        if x.fields.customfield_16736 != None:
                            ib_tracking_num = x.fields.customfield_16736
                            self.ic_component_metrics[i.name]['inbound_len']+= 1
                            response = self.fedex.track_shipment(ib_tracking_num, return_raw=True)

                            try:
                                recipient_zip = self.zipDB.find_zip(city=response['output']['completeTrackResults'][0]['trackResults'][0]['recipientInformation']['address']['city'].lower(), \
                                                                    state=response['output']['completeTrackResults'][0]['trackResults'][0]['recipientInformation']['address']['stateOrProvinceCode'])[0].zip
                                sender_zip = self.zipDB.find_zip(city=response['output']['completeTrackResults'][0]['trackResults'][0]['shipperInformation']['address']['city'].lower(), \
                                                                state=response['output']['completeTrackResults'][0]['trackResults'][0]['shipperInformation']['address']['stateOrProvinceCode'])[0].zip
                            except KeyError:
                                recipient_zip = None
                                sender_zip = None

                            cost = float(self.fedex.estimate(sender_zip, recipient_zip, 5, 1000)['totalNetCharge'])
                            self.ic_component_metrics[i.name]['cost_avg'] += self.ic_component_metrics[i.name]['cost_avg'] 
                        if x.fields.customfield_16737 != None:
                            ob_tracking_num = x.fields.customfield_16737
                            self.ic_component_metrics[i.name]['outbound_len']+= 1
                            
                elif len(issues):
                    self.ic_component_metrics[i.name] = {'total_issues':len(issues), 'time': 0}
                    for x in issues:
                        date_created = x.fields.created[0:x.fields.created.index('T')]
                        date_resolved = x.fields.resolutiondate[0:x.fields.resolutiondate.index('T')]
                        date_delta = datetime.strptime(date_resolved, "%Y-%m-%d").date() - datetime.strptime(date_created, "%Y-%m-%d").date()
                        self.ic_component_metrics[i.name]['time'] += date_delta.days

                    self.ic_component_metrics[i.name]['time'] /= len(issues)
                bar.next()




from jira import JIRA
from datetime import datetime

class IC:
    def __init__(self, auth_username, password, ic_username):
        self.jira = JIRA('https://jira.yelpcorp.com', auth=(auth_username, password))
        self.username = ic_username
        self.components = self.jira_obj.project_components("HELPDESK")
        self.ic_component_metrics = {}

    def fdx_ic_metrics(self, offset=30):
        """Search Jira for user tickets with Fedex, Fedex Shipping, or Fedex Pickup Component"""
        
        self.fdx_issues = self.jira.search_issues(f'project = HELPDESK AND status in (Resolved, Closed) AND assignee = {self.username} AND \
                                            resolutiondate >= -{offset}d and component in(Fedex, "Fedex Shipping", "Fedex Pickup")')
        
        for i in self.fdx_issues:
            if i.fields.customfield_16736 != None:
                self.ib_tracking_nums.append(i.fields.customfield_16736)
            if i.fields.customfield_16737 != None:
                self.ob_tracking_nums.append(i.fields.customfield_16737)

    def component_metrics(self, offset=30):
        """Grab IC Component metrics from HELPDESK Project"""

        for i in self.components:
            issues = self.jira.search_issues(f'project = HELPDESK AND status in (Resolved, Closed) AND assignee = {self.username} AND \
                                            resolutiondate >= -{offset}d and component in("{i.name}")')
            for x in issues:
                date_created = x.fields.created[0:x.fields.created.index('T')]
                date_resolved = x.fields.resolutiondate[0:x.fields.resolutiondate.index('T')]
                date_delta = datetime.strptime(date_resolved).date() - datetime.strptime(date_created).date()

            self.ic_component_metrics[i.name] == {'total_issues':len(issues), 'time':date_delta.days}




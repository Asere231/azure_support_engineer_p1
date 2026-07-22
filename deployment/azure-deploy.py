import subprocess
import os
import re
import json
from pydantic import BaseModel

# Project 1 modules.
import util

class Subnet(BaseModel):
    name: str = 'default-subnet-name'
    netip: str = '10.0.10.0/24'
    # TODO: Add more params as needed. For more info see
    # https://pydantic.dev/docs/validation/latest/get-started/

class VM(BaseModel):
    name: str           = 'vm'
    os: str             = 'Ubuntu2204'
    size: str           = 'Standard_B2ats_v2'
    storage_sku: str    = 'Standard_LRS'
    admin_user: str     = 'azureuser'
    subnet: Subnet

class Azure_Deployment():

    def __init__(self):
        # Get subscription id of the current azure user, so we can run commands
        # targeting it.
        cmd_list = [
            'az', 'account', 'show', '--query', 'id', '--output', 'tsv'
        ]
        self.subscription   = util.run_cmd(cmd_list).stdout.strip()

        # Default to development deployment.
        self.name           = 'p1-dev'

        # Resource group.
        self.rg_name        = f'rg-{self.name}'
        self.rg_location    = 'canadaeast'

        # Virtual network.
        self.vnet_name      = f'vnet-{self.name}'
        self.vnet_netip     = '10.0.0.0/16'

        # Network security group.
        self.nsg_auth_name  = f'nsg-{self.name}-jwt-auth'
        
        # Subnets for our VNet.
        # JWT Authentication.
        self.subnet_auth = Subnet.model_validate({
            'name': 'sub-jwt-auth',
            'netip': '10.0.1.0/24'
        })
        # Private endpoints subnet.
        self.subnet_private = Subnet.model_validate({
            'name': 'sub-private-eps',
            'netip': '10.0.2.0/24'
        })

        # Virtual machines.
        # JWT Authentication.
        self.vm_jwt_auth = VM.model_validate({
            'name': 'vm-jwt-auth',
            'subnet': {
                'name':  self.subnet_auth.name,
                # TODO: Remove or use this static IP.
                'netip': '10.0.1.2/32'
            }
        })

        # Log analytics workspace.
        self.law_name       = f'law_{self.name}'

        # Diagnostic settings.
        self.ds_vnet_name    = f'ds_{self.name}_vnet'
        self.ds_nsg_name    = f'ds_{self.name}_nsg'

        # Data collection settings.
        self.dcr_vm_jwt_auth_name = f'dcr_jwt_auth_vm'
        self.dc_vm_jwt_auth_name = f'dc_jwt_auth_vm'

    def production_configs(self):
        # Azure production deployment configs.
        self.rg_name     = 'rg-p1-prod'
        self.rg_location = 'canadaeast'

    def deploy_all(self):
        self.deploy_rg()
        self.deploy_network()
        self.deploy_vm_auth()

    # Check for RG and creates it if DNE. Also Sets up user roles for members 
    # listed in the roles.json.
    def deploy_rg(self):
        print(util.f.bold('Resource Group Deployment'))
        # Check for existing RG.
        # 'az group show --name "{self.rg_name}"'

        # Should output RG info as a json, if RG already exists.
        # Else an error with Code: ResourceGroupNotFound will be returned.
        cmd_list = [
            'az', 'group', 'show', '--name', self.rg_name
        ]
        needs_create = False
        try:
            result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=False)
            print(util.f.info('Info') + f': RG {util.f.item(self.rg_name)} already exists. Skipping recreation')
            # TODO: Probably ask if the user wants to rename this deployment, 
            # or override the existing RG and its resources.
        except subprocess.CalledProcessError as e:
            if re.search(r'(ResourceGroupNotFound)', e.stderr):
                print(util.f.info('Info') + f': RG {util.f.item(self.rg_name)} not found')
                needs_create = True
            else:
                print(util.f.error('Error') + ': Uncaught CalledProcessError ' + util.f.item(f'{e.returncode}'))
                raise e

        # Create RG.    
        cmd_list = [
            'az', 'group', 'create', 
            '--name', self.rg_name, 
            '--location', self.rg_location, 
            '--output', 'table'
            # TODO: Check if we really want to output as table, vs json vs tsv
        ]
        if needs_create:
            result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)
            # TODO: Print out command output (a json of the new RG).

            # Setup member roles for project team members.
            file_path = 'deployment/roles.json'
            try:
                with open(file_path, 'r') as file:
                    members_data = json.load(file)
            except FileNotFoundError as e:
                print(util.f.warn('Warning') + ": failed to open " + util.f.item(file_path) + \
                      '. Skipping role assignments')
                members_data = {'members': []}

            for member in members_data["members"]:
                # Create the correct command to run, then try to run it.
                cmd_list = [
                    'az', 'role', 'assignment', 'create', 
                    '--assignee', member['--assignee'],
                    '--role', member['--role'],
                    '--scope', f'/subscriptions/{self.subscription}/resourceGroups/{self.rg_name}'
                ]
                # Attempt command.
                if util.run_cmd(cmd_list, True, True) != None:
                    # Okay, the last command worked, fetch this user's name and
                    # print thier name in a success message.
                    cmd_list = [
                        'az', 'ad', 'user', 'show',
                        '--id', member['--assignee'],
                        '--output', 'json'
                    ]
                    result = util.run_cmd(cmd_list, False, True)
                    if result != None:
                        # Convert to json.
                        user_info = json.loads(result.stdout)
                        print(util.f.info('Info') + ': Added ' + util.f.item(user_info['displayName']) + \
                              ' (' + util.f.item(user_info['mail']) + ') as a ' + util.f.item(member['--role']))
                    else:
                        # Weird case where the command for adding a user succeds, but we fail to get thier info.
                        print(util.f.info('Info') + ': Added ' + util.f.item(member['name']) + \
                              ' as a ' + util.f.item(member['--role']))
                else:
                    # Failed to add user.
                    print(util.f.warn('Warning') + ': Failed to add ' + util.f.item(member['--role']) + \
                          ' role for ' + util.f.item(member['user']) + ". Skipping this user")
        print('')

    # Check for virtual network and creates it if DNE.
    def deploy_network(self):
        print(util.f.bold('Virtual Network Deployment'))
        # Check for existing VNet.
        # 'az network vnet show --resource-group {self.rg_name} --name {self.vnet_name}'

        # Should output VNet info as a json, if it already exists.
        # Else an error with Code: ResourceNotFound will be returned.
        cmd_list = [
            'az', 'network', 'vnet', 'show',
            '--resource-group', self.rg_name,
            '--name',           self.vnet_name
        ]
        needs_create = False
        try:
            result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=False)
            print(util.f.info('Info') + f': VNet {util.f.item(self.vnet_name)} already exists. Skipping recreation')
            # TODO: Probably ask if the user wants to rename this deployment, 
            # or override the existing VNet.
        except subprocess.CalledProcessError as e:
            if re.search(r'(ResourceNotFound)', e.stderr):
                print(util.f.info('Info') + f': VNet {util.f.item(self.vnet_name)} not found')
                needs_create = True
            else:
                print(util.f.error('Error') + ': Uncaught CalledProcessError ' + util.f.item(f'{e.returncode}'))
                raise e

        # Create VNet. For more info see
        # https://learn.microsoft.com/en-us/cli/azure/azure-cli-vm-tutorial-2?view=azure-cli-latest&tabs=bash    
        cmd_list = [
            'az', 'network', 'vnet', 'create',
            '--resource-group',     self.rg_name,
            '--name',               self.vnet_name,
            '--address-prefixes',   self.vnet_netip,
            # 1st subnet, for JWT authentication.
            '--subnet-name',        self.subnet_auth.name,
            '--subnet-prefixes',    self.subnet_auth.netip,

            # TODO: Check if we really want to output as table, vs json vs tsv
            '--output', 'table'
        ]
        if needs_create:
            result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)
            # TODO: Print out command output (a json of the new VNet).

            # TODO: Instead of running this as a seperate command, add it to the VNet creation.
            # I did it this way to test adding a new subnet to an existing VNet.
            cmd_list = [
                'az', 'network', 'vnet', 'subnet', 'create',
                '--resource-group',     self.rg_name,
                '--vnet-name',          self.vnet_name,
                # Subnet params.
                '--name',               self.subnet_private.name,
                '--address-prefixes',   self.subnet_private.netip
                # TODO: Create additional NSG for this subnet and assicated with:
                # '--network-security-group', self.SOME_NSG
            ]
            result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)

        # Setup NSG.
        needs_create = False
        # Has NSG already?
        # Should output NSG info as a json, if it already exists.
        # Else an error with Code: ResourceNotFound will be returned.
        cmd_list = [
            'az', 'network', 'nsg', 'show',
            '--resource-group', self.rg_name,
            '--name',           self.nsg_auth_name
        ]
        try:
            result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=False)
            print(util.f.info('Info') + f': NSG {util.f.item(self.nsg_auth_name)} already exists. Skipping recreation')
            # TODO: Probably ask if the user wants to rename this deployment, 
            # or override the existing NSG.
        except subprocess.CalledProcessError as e:
            if re.search(r'(ResourceNotFound)', e.stderr):
                print(util.f.info('Info') + f': NSG {util.f.item(self.nsg_auth_name)} not found')
                needs_create = True
            else:
                print(util.f.error('Error') + ': Uncaught CalledProcessError ' + util.f.item(f'{e.returncode}'))
                raise e
        # Create NSG. For more info see
        # https://learn.microsoft.com/en-us/cli/azure/network/nsg?view=azure-cli-latest 
        cmd_list = [
            'az', 'network', 'nsg', 'create',
            '--resource-group',     self.rg_name,
            '--name',               self.nsg_auth_name,

            # TODO: Check if we really want to output as table, vs json vs tsv
            '--output', 'table'
        ]
        if needs_create:
            result = util.run_cmd(cmd_list, True)
            # TODO: Print out command output (a json of the new VNet).

            # Then, we need to create our NSG rules.
            # TODO: Use a Pydatic model and new NSG class member to store rules
            # in a list for more easy deployment and editing, instead of hard
            # coding here...
            cmd_list = [
                'az', 'network', 'nsg', 'rule', 'create',
                '--resource-group',             self.rg_name,
                '--nsg-name',                   self.nsg_auth_name,
                # Rule params.
                '--name',                       'Allow_FastAPI_HTTP_connections',
                '--description',                'Used to access the JWT auth. VM.',
                '--priority',                   '200',
                '--direction',                  'Inbound',
                '--access',                     'Allow',
                '--protocol',                   'Tcp',
                '--destination-port-ranges',    '8080',
                # All other params default to '*', wildcard for all.

                # TODO: Check if we really want to output as table, vs json vs tsv
                '--output', 'table'
            ]
            result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)
            cmd_list = [
                'az', 'network', 'nsg', 'rule', 'create',
                '--resource-group',             self.rg_name,
                '--nsg-name',                   self.nsg_auth_name,
                # Rule params.
                '--name',                       'Allow_SSH',
                '--description',                'passes ssh through',
                '--priority',                   '110',
                '--direction',                  'Inbound',
                '--access',                     'Allow',
                '--protocol',                   'Tcp',
                '--destination-port-ranges',    '22',
                # All other params default to '*', wildcard for all.

                # TODO: Check if we really want to output as table, vs json vs tsv
                '--output', 'table'
            ]
            result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)

            # After creating the NSG, we need to assign it to the correct subnet.
            cmd_list = [
                'az', 'network', 'vnet', 'subnet', 'update',
                '--resource-group',             self.rg_name,
                '--name',                       self.subnet_auth.name,
                '--vnet-name',                  self.vnet_name,
                '--network-security-group',     self.nsg_auth_name,
                # TODO: Check if we really want to output as table, vs json vs tsv
                '--output', 'table'
            ]
            result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)

            # TODO: Setup routes between future subnets.

        # TODO: Setup with correct subnets, security groups, routes, etc.
        print('')

    # Deploys the JWT VM, and spin up the FASTAPI docker container.
    def deploy_vm_auth(self):
        print(util.f.bold('JWT Authorization VM Deployment'))
        # Check for existing VM.
        cmd_list = [
                'az', 'vm', 'show', 
                '--resource-group', self.rg_name, 
                '--name', self.vm_jwt_auth.name,
                '--output', 'tsv'
            ]
        needs_create = False
        result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=True)
        if result == None or not result.stdout.strip():
            print(util.f.info('Info') + f': VM {util.f.item(self.vm_jwt_auth.name)} not found')
            needs_create = True
        else:
            # TODO: Probably ask if the user wants to rename this deployment, 
            # or override the existing VNet.
            print(util.f.info('Info') + f': VM {util.f.item(self.vm_jwt_auth.name)} already exists. Skipping recreation')

        if needs_create:
            cmd_list = [
                'az', 'vm', 'create', 
                '--resource-group', self.rg_name,
                '--location',       self.rg_location,
                '--name',           self.vm_jwt_auth.name,
                '--image',          self.vm_jwt_auth.os,
                '--size',           self.vm_jwt_auth.size,
                '--storage-sku',    self.vm_jwt_auth.storage_sku,
                '--admin-username', self.vm_jwt_auth.admin_user,
                # Network.
                '--vnet-name',      self.vnet_name,
                '--subnet',         self.vm_jwt_auth.subnet.name,
                '--nsg',            '',
                # Other.
                '--boot-diagnostics-storage', '',
                '--generate-ssh-keys',
                '--verbose', '--output', 'json'
            ]
            result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)
            # TODO: Print out command output (a json of the new VNet).

            # Get bootstrap file path.
            script_dir              = os.path.dirname(os.path.abspath(__file__))
            source_bootstrap_path   = os.path.join(script_dir, 'bootstrap_auth_jwt.sh')

            cmd_list = [
                'az', 'vm', 'run-command', 'invoke',
                '--resource-group', self.rg_name,
                '--name',           self.vm_jwt_auth.name,
                '--command-id',     'RunShellScript', 
                '--scripts',        f'@{source_bootstrap_path}',
                '--query',          'value[0].message',
                # TODO: Check if we really want to output as table, vs json vs tsv
                '--output',         'table'
            ]
            # TODO: Swap bootstrap_auth_jwt.sh to use SCP to transfer files instead of cloning
            # the entire project git repo.
            result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)

        print('')

# Create private endpoint server.
# TODO:

# Setup Azure resource monitoring.
# TODO:
    def deploy_monitoring(self):
        print(util.f.bold('Log Analytics Workspace Deployment'))
        
        # Okay, this project requires us to setup a log analytics workspace (LAW),
        # record SLI using metrics. We should also setup application level monitoring
        # with the use of the VM AZ extention. Once setup, (we should get log data from
        # NSG traffic, Middleware on request like the JWT, VM metrics at both the platform
        # and application level) use Kusto Query language to select/filter logs.

        # TODO: LOOK INTO THE GRAFANA DASHBOARD, MAYBE SETUP A PROMETHEOUS CONTAINER TO
        # CHECK VM HEALTH.

        # TODO: Check for existing LAW, handle logic.
        # Create new LAW for p1.
        cmd_list = [
            'az', 'monitor', 'log-analytics', 'workspace', 'create',
            '--name',           self.law_name,
            '--resource-group', self.rg_name,
            '--retention-time', 30 # In days.
        ]
        result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)
        # Get its ID.
        cmd_list = [
            'az', 'monitor', 'log-analytics', 'workspace', 'show',
            '--name',           self.law_name,
            '--resource-group', self.rg_name,
            '--query'           'id',
            '--output',         'tsv'
        ]
        result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=False)
        law_id = result.stdout.strip()

        # Setup NSG log accesses.
        # We first need to pull the id of the nsg we're going to add a monitoring rule for.
        cmd_list = [
            'az', 'network', 'nsg', 'show',
            '--resource-group', self.rg_name,
            '--name',           self.nsg_auth_name,
            '--query',          'id',
            '--output',         'tsv'
        ]
        result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=False)
        # Get ID of NSG now.
        nsg_id = result.stdout.strip()

        cmd_list = [
            'az', 'monitor', 'diagnostic-settings', 'create',
            '--name',           self.ds_nsg_name,
            '--resource',       nsg_id,
            '--workspace',      self.law_name,
            # TODO: Move category to self option for DS.
            '--logs',             '[{"categoryGroup": "allLogs", "enabled": true}]'
        ]
        result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)

        # Setup VNet DS.
        # We first need to pull the id of the VNet we're going to add a monitoring rule for.
        cmd_list = [
            'az', 'network', 'vnet', 'show',
            '--resource-group', self.rg_name,
            '--name',           self.vnet_name,
            '--query',          'id',
            '--output',         'tsv'
        ]
        result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=False)
        # Get ID of VNet now.
        vnet_id = result.stdout.strip()

        cmd_list = [
            'az', 'monitor', 'diagnostic-settings', 'create',
            '--name',           self.ds_vnet_name,
            '--resource',       vnet_id,
            '--workspace',      self.law_name,
            # TODO: Move category to self option for DS.
            '--logs',           '[{"categoryGroup": "allLogs", "enabled": true}]',
            '--metrics',        '[{"category": "AllMetrics", "enabled": true}]'
        ]
        result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)

        # Alright now setup the AZ monitoring client for the JWT VM.
        # TODO: Container concerns?
        # Get VM ID.
        cmd_list = [
            'az', 'vm', 'show',
            '--resource-group', self.rg_name,
            '--name',           self.vm_jwt_auth.name,
            '--query',          'id',
            '--output',         'tsv'
        ]
        result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=False)
        vm_auth_id = result.stdout.strip()

        # Create new data collection rule.

        # Load our dcr_jwt_auth.json file, and update a few params before creating a temp
        # file to use for DC creation.
        file_path = 'deployment/dcr_jwt_auth.json'
        with open(file_path, 'r') as file:
            dcr_data = json.load(file)
        dcr_data['location'] = f'"{self.rg_location}"'
        dcr_data['destinations']['logAnalytics'][0]['workspaceResourceId'] = law_id
        # Write to file.
        with open('deployment/temp/dcr_jwt_auth.json', 'w') as file:
            json.dump(dcr_data, file)

        # Create.
        cmd_list = [
            'az', 'monitor', 'data-collection', 'rule', 'create',
            '--resource-group', self.rg_name,
            '--name',           self.dcr_vm_jwt_auth_name,
            '--rule-file',      'deployment\\temp\\dcr_jwt_auth.json'
        ]
        # NOTE: Running this command for the first time might require entering a 'yes' to
        # install required extentions. Can avoid this with by running 'az config set extension.dynamic_install_allow_preview=true'
        result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)
        # Cleanup temp file.
        result = util.run_cmd(['rm', 'deployment/temp/dcr_jwt_auth.json'], print_cmd=False, allow_fail=False)
        # Get DCR id.
        cmd_list = [
            'az', 'monitor', 'data-collection', 'rule', 'show',
            '--resource-group', self.rg_name,
            '--name',           self.dcr_vm_jwt_auth_name,
            '--query',          'id',
            '--output',         'tsv'
        ]
        result = util.run_cmd(cmd_list, print_cmd=False, allow_fail=False)
        dcr_id = result.stdout.strip()

        # Associate DCR to VM.
        cmd_list = [
            'az', 'monitor', 'data-collection', 'rule', 'association', 'create',
            '--name',           self.dc_vm_jwt_auth_name,
            '--resource',       vm_auth_id,
            '--rule-id',        dcr_id,
            '--kind',           'Linux'
        ]
        result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)

        # And Finally, add the vm extention to actaully get application level info.
        cmd_list = [
            'az', 'vm', 'extension',    'set',
            '--resource-group',         self.rg_name,
            '--vm-name',                self.vm_jwt_auth.name,
            '--name',                   'AzureMonitorLinuxAgent',
            '--publisher',              'Microsoft.Azure.Monitor'
        ]
        result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=False)

        print('')

# TODO: Add main function, improve read-ablility of code.
try:
    test = Azure_Deployment()
    test.deploy_all()
except Exception as e:
    print(util.f.error('Error') + ': Failed to deploy project 1. Attempting to clean up all resources.')
    cmd_list = [
        'az', 'group', 'delete',
        '--name', test.rg_name,
        '--no-wait', '--yes'
    ]
    result = util.run_cmd(cmd_list, print_cmd=True, allow_fail=True)
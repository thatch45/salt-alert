'''
All salt configuration loading and defaults should be in this module
'''
# Import python modules
import os
import sys
# Import salt libs
import salt.config
import salt.crypt

def alert_config(path):
    '''
    Reads in the alert configuration file and sets up default options
    '''
    opts = {'interface': '0.0.0.0',
            'worker_threads': 3,
            'worker_start_port': '46056',
            'ret_port': '4507',
            'root_dir': '/',
            'pki_dir': '/etc/salt/pki',
            'cachedir': '/var/cache/salt',
            'file_roots': {
                'base': ['/srv/salt'],
                },
            'file_buffer_size': 1048576,
            'hash_type': 'md5',
            'conf_file': path,
            'open_mode': False,
            'auto_accept': False,
            'renderer': 'yaml_jinja',
            'order_masters': False,
            'log_file': '/var/log/salt/alert',
            'log_level': 'warning',
            'log_granular_levels': {},
            'cluster_masters': [],
            'cluster_mode': 'paranoid',
            }

    salt.config.load_config(opts, path, 'SALT_ALERT_CONFIG')

    opts['aes'] = salt.crypt.Crypticle.generate_key_string()

    # Prepend root_dir to other paths
    salt.config.prepend_root_dir(opts, ['pki_dir', 'cachedir', 'log_file'])

    # Enabling open mode requires that the value be set to True, and nothing
    # else!
    if opts['open_mode']:
        if opts['open_mode'] == True:
            opts['open_mode'] = True
        else:
            opts['open_mode'] = False
    if opts['auto_accept']:
        if opts['auto_accept'] == True:
            opts['auto_accept'] = True
        else:
            opts['auto_accept'] = False
    return opts

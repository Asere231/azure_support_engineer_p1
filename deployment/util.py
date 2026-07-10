import subprocess

# Used to access formating functions.
class f():
    # Special characters for printing to console with extra formating.
    __char_color_red    = '\033[91m'
    __char_color_yellow = '\033[93m'
    __char_color_cyan   = '\033[96m'
    __char_color_blue   = '\033[34m'
    __char_underline    = '\033[4m'
    __char_bold         = '\033[1m'
    __char_end          = '\033[0m'

    # Formats passed string for an error/warning/info/etc.
    def error(s: str) -> str:
        return f.__char_color_red + s + f.__char_end
    def warn(s: str) -> str:
        return f.__char_color_yellow + s + f.__char_end
    def info(s: str) -> str:
        return f.__char_color_cyan + s + f.__char_end
    def item(s: str) -> str:
        return f.__char_color_blue + s + f.__char_end
    def bold(s: str) -> str:
        return f.__char_bold + s + f.__char_end
    def uline(s: str) -> str:
        return f.__char_underline + s + f.__char_end

# Static function for wrapping a run exception so we can print any errors 
# to the console before exiting the program.
def run_cmd(cmd_list, print_cmd=False, allow_fail=True):
    try:
        if print_cmd:
            print(f.info('Info') + ': Running Command ' + f.item(' '.join(cmd_list)))
        return subprocess.run(cmd_list, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        if allow_fail:
            return None
        print(f.error('Error') + ': Command ' + f.item(' '.join(cmd_list)) + ' failed')
        print('Returned (' + f.warn(f'{e.returncode}') + '): ' + f.warn(f'{e.stderr}'))
        raise e
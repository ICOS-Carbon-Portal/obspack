# Related third party imports.
import requests
# Local application/library specific imports.
from icoscp_obspack.constants import icons as i


def progress_bar(operation: str = None, current: int = None, total: int = None,
                 bar_length: int = 20) -> None:
    """
    Outputs a loading-like bar for various operations.

    Credits to: https://stackoverflow.com/a/37630397
    """
    if operation == 'Getting file metadata':
        prepender = f'{operation}: Please wait'
    else:
        exit('Unknown operation.\nExiting...')
    fraction = current / total
    arrow = int(fraction * bar_length - 1) * '-' + '>'
    padding = int(bar_length - len(arrow)) * ' '
    if current == total:
        prepender = f'\t\t{operation}: Completed'
        ending = f' {i.ICON_CHECK}\n'
    else:
        ending = '\r'
    progress = str(
        f'{prepender} '
        f'[{arrow}{padding}] {int(fraction*100)}%'
    )
    import time
    time.sleep(0.2)
    print(200*' ', end='\r', flush=True)
    print(progress, end=ending, flush=True)


def new_file_info(uri: str = None):
    response = requests.get(uri, headers={'Accept': 'application/json'})
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print('Error fetching data')
        return 'Error'

import time
from hatena import ServerLog, Silent
from DB import Database
from Hatenatools import TMB

def handle_flipnote_upload(binary_data, query_args, client_ip):
    """
    Handles the actual logic of a Flipnote upload.
    
    :param binary_data: The raw PPM file bytes from the request body.
    :param query_args: A dictionary of query parameters (e.g., {'channel': '123'}).
    :param client_ip: The string IP address of the DSi.
    :return: A tuple of (status_code, response_body_bytes)
    """
    
    # 1. Extract Channel (DSi sends this in the URL)
    channel = ""
    if "channel" in query_args:
        # Handle cases where query_args might be a list (like in Flask/Django)
        val = query_args["channel"]
        channel = val[0] if isinstance(val, list) else val
    
    # 2. Add to Database
    # Database.AddFlipnote must be updated to handle 'bytes' for data
    # and 'str' for channel.
    result = Database.AddFlipnote(binary_data, channel)
    
    if result:
        # result[1] is typically the filename/FSID
        filename = result[1]
        ServerLog.write(f"{client_ip} successfully uploaded \"{filename}.ppm\"", Silent)
        return 200, b""
    else:
        ServerLog.write(f"{client_ip} tried to upload a flipnote, but failed...", Silent)
        # 500 status tells the DSi there was a server error
        return 500, b""

# Example of how you'd call this in a generic Python script/handler:
# status, body = handle_flipnote_upload(raw_post_bytes, request_params, remote_addr)

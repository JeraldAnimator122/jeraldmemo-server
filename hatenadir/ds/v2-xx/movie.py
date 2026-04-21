import os
import urllib.parse
from hatena import Log, ServerLog, Silent, NotFound
from DB import Database
from Hatenatools import TMB

# Templates moved to a separate dictionary for cleaner access
TEMPLATES = {
    "DetailsPage": """<html>
    <head>
        <title>Flipnote by %%Username%%</title>
        <meta name="upperlink" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.ppm">
        <meta name="starbutton" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star">
        <meta name="starbutton1" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star?starcolor=green,9001">
        <meta name="starbutton2" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star?starcolor=red,9001">
        <meta name="starbutton3" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star?starcolor=blue,9001">
        <meta name="starbutton4" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.star?starcolor=purple,9001">
        <meta name="savebutton" content="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.ppm">
        <link rel="stylesheet" href="http://flipnote.hatena.com/css/ds/basic.css">
    </head>
    <body>
        <table width="240" border="0" cellspacing="0" cellpadding="0" class="tab">
            <tr>
                <td class="tabon" align="center"><div class="on">Description</div></td>
                <td class="taboff" align="center">
                    <a class="taboff" href="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.htm?mode=commentshalfsize">Comments(%%CommentCount%%)</a>
                </td>
            </tr>
        </table>
        <div class="pad5b"></div>%%Spinoff%%
        <table width="226" border="0" cellspacing="0" cellpadding="0" class="detail">%%PageEntries%%</table>
    </body>
</html>""",
    "Spinoff1": '<div class="notice2">Spin-off.<br><a href="http://flipnote.hatena.com/ds/v2-xx/movie/%%CreatorID%%/%%Filename%%.htm">Original</a></div>',
    "Spinoff2": '<div class="notice2">Spin-off.</div>',
    "Entry": '<tr><th width="90"><div align="left">%%Name%%</div></th><td width="136"><div align="right">%%Content%%</div></td></tr>',
    "Separator": '<tr><td colspan="2"><div class="hr"></div></td></tr>'
}

def handle_movie_request(path_parts, query_args, headers, client_ip):
    """
    Router for /movie/ requests.
    path_parts: list of strings (e.g. ['CREATOR_ID', 'FILE.ppm'])
    """
    
    # 1. Base /movie/ access (Denied)
    if not path_parts or path_parts[0] == "":
        return 403, b"403 - Denied access"

    creator_id = path_parts[0]

    # 2. Check if Creator Exists
    if not Database.CreatorExists(creator_id):
        return 404, b"404 - Not Found"

    # 3. Creator Folder access (Denied)
    if len(path_parts) == 1 or path_parts[1] == "":
        return 403, b"403 - Denied access"

    filename_full = path_parts[1]
    filename_raw = ".".join(filename_full.split(".")[:-1])
    filetype = filename_full.split(".")[-1].lower()

    # 4. Check if Flipnote Exists
    if not Database.FlipnoteExists(creator_id, filename_raw):
        return 404, b"404 - Not Found"

    # --- ROUTE LOGIC BY EXTENSION ---
    
    if filetype == "ppm":
        # Log and add View
        Log(client_ip, "/".join(path_parts))
        Database.AddView(creator_id, filename_raw)
        
        data = Database.GetFlipnotePPM(creator_id, filename_raw)
        return 200, data # binary data

    elif filetype == "info":
        return 200, b"0\n0\n"

    elif filetype == "htm":
        html_content = generate_details_page(creator_id, filename_raw)
        return 200, html_content.encode("utf-8")

    elif filetype == "star":
        # Handle X-Hatena-Star-Count header (Keys in Python 3 headers are lowercase in most frameworks)
        star_header = headers.get("x-hatena-star-count") or headers.get("X-Hatena-Star-Count")
        color = query_args.get('starcolor', ["yellow"])[0]

        if not star_header:
            ServerLog.write(f"{client_ip} missing star header", Silent)
            return 403, b"403 - Missing Star Header"

        try:
            amount = int(star_header)
            if not (1 <= amount <= 65535): raise ValueError
        except ValueError:
            return 403, b"403 - Invalid Star Count"

        if Database.AddStar(creator_id, filename_raw, amount, color):
            ServerLog.write(f"{client_ip} added {amount} {color} stars", Silent)
            return 200, b"Success"
        return 500, b"500 - Failed to add stars"

    elif filetype == "dl":
        Database.AddDownload(creator_id, filename_raw)
        return 200, b"Noted ;)"

    return 403, b"403 - Denied"

def generate_details_page(creator_id, filename):
    flipnote = Database.GetFlipnote(creator_id, filename)
    if not flipnote: return "Missing File"
    
    # tmb_data is bytes
    tmb_data = Database.GetFlipnoteTMB(creator_id, filename)
    tmb = TMB().Read(tmb_data)
    
    # Spinoff Logic
    spinoff_html = ""
    if tmb.OriginalAuthorID != tmb.EditorAuthorID or tmb.OriginalFilename != tmb.CurrentFilename:
        orig_fn = tmb.OriginalFilename[:-4] if tmb.OriginalFilename.endswith(".ppm") else tmb.OriginalFilename
        if Database.FlipnoteExists(tmb.OriginalAuthorID, orig_fn):
            spinoff_html = TEMPLATES["Spinoff1"].replace("%%CreatorID%%", tmb.OriginalAuthorID).replace("%%Filename%%", orig_fn)
        else:
            spinoff_html = TEMPLATES["Spinoff2"]

    entries = []
    
    # Entry Helper
    def add_entry(name, content):
        entries.append(TEMPLATES["Entry"].replace("%%Name%%", name).replace("%%Content%%", content))

    add_entry("Creator", f'<a href="http://flipnote.hatena.com/ds/v2-xx/{creator_id}/profile.htm">{tmb.Username}</a>')
    
    # Stars (Yellow, Green, Red, Blue, Purple correspond to indices 2,3,4,5,6)
    star_box = ""
    for i in range(5):
        star_box += f'<span class="star{i}c">\u2605</span> <span class="star{i}">{flipnote[i+2]}</span><br/>'
    add_entry("Stars", star_box)
    
    add_entry("Views", str(flipnote[1]))
    add_entry("Downloads", str(flipnote[8]))

    if flipnote[7]: # Channel
        add_entry("Channel", f'<a href="http://flipnote.hatena.com/ds/v2-xx/ch/{flipnote[7]}.uls">{flipnote[7]}</a>')

    return TEMPLATES["DetailsPage"].replace("%%CreatorID%%", creator_id)\
                                  .replace("%%Filename%%", filename)\
                                  .replace("%%CommentCount%%", "0")\
                                  .replace("%%Spinoff%%", spinoff_html)\
                                  .replace("%%PageEntries%%", TEMPLATES["Separator"].join(entries))

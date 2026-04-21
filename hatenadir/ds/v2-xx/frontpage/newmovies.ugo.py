import time
import threading
from hatena import Log, NotFound
from DB import Database
from Hatenatools import UGO

class NewMoviesManager:
    def __init__(self):
        self.pages = []  # List of packed UGO binary data
        self.newest_flip_id = None
        self.lock = threading.Lock()
        
        # Start the background update loop
        # This replaces reactor.callLater
        updater = threading.Thread(target=self._update_loop, daemon=True)
        updater.start()

    def _update_loop(self):
        """Background loop to refresh the UGO cache every 60 seconds."""
        # Initial delay to let DB/Terminal stabilize (replaces the 4s delay)
        time.sleep(4)
        
        while True:
            try:
                # Check if Database has new content
                current_newest = Database.Newest[0] if Database.Newest else None
                
                if self.newest_flip_id != current_newest:
                    self.newest_flip_id = current_newest
                    self.refresh_cache(Database.Newest)
            except Exception as e:
                print(f"Error in background update: {e}")
            
            time.sleep(60)

    def refresh_cache(self, flipnotes):
        """Creates the binary UGO pages and stores them in memory."""
        new_pages = []
        total_count = len(flipnotes)
        
        # Calculate page count (max 10 for DSi performance/memory)
        # Using integer division // for Python 3
        page_limit = min(((total_count - 1) // 50 + 1), 10)
        
        for i in range(page_limit):
            is_last = (i == page_limit - 1)
            chunk = flipnotes[i * 50 : (i + 1) * 50]
            packed_page = self.make_page(chunk, i + 1, not is_last, total_count)
            new_pages.append(packed_page)
        
        # Thread-safe update of the shared pages list
        with self.lock:
            self.pages = new_pages
        
        print(time.strftime("[%H:%M:%S] Updated newmovies.ugo cache"))

    def make_page(self, flipnote_refs, page_num, has_next, total_count):
        """Builds a UGO object and packs it into DSi binary format."""
        ugo = UGO()
        ugo.Loaded = True
        ugo.Items = []
        
        # 1. Meta / Layout
        ugo.Items.append(("layout", [2, 1]))
        # Python 3 strings are already unicode, so standard list is fine
        ugo.Items.append(("topscreen text", [
            "New Flipnotes", 
            "Flipnotes", 
            str(total_count), 
            "", 
            "The newest Flipnotes submitted."
        ], 0))
        
        # 2. Categories (Navigation Tabs)
        base_url = "http://flipnote.hatena.com/ds/v2-xx/frontpage"
        ugo.Items.append(("category", f"{base_url}/hotmovies.uls", "Most Popular", False))
        ugo.Items.append(("category", f"{base_url}/likedmovies.uls", "Most Liked", False))
        ugo.Items.append(("category", f"{base_url}/newmovies.uls", "New Flipnotes", True))
        
        # 3. Post Flipnote Button (Type 3 / Unknown in original script)
        # B64 encoded string: "Post Flipnote"
        ugo.Items.append(("unknown", ["3", "http://flipnote.hatena.com/ds/v2-xx/help/post_howto.htm", "UABvAHMAdAAgAEYAbABpAHAAbgBvAHQAZQA="]))
        
        # 4. Previous Page Button
        if page_num > 1:
            prev_url = f"{base_url}/newmovies.uls?page={page_num - 1}"
            ugo.Items.append(("button", 115, "Previous", prev_url, ["", ""], None))
        
        # 5. Flipnote Entries
        for creator_id, filename in flipnote_refs:
            # Database.GetFlipnote returns [filename, views, stars, ...]
            # stars is index 2
            flip_data = Database.GetFlipnote(creator_id, filename)
            star_count = str(flip_data[2]) if flip_data else "0"
            
            # Button trait 3 is a Flipnote thumbnail
            # Extra data is [stars, unknown, unknown, unknown]
            tmb_data = Database.GetFlipnoteTMB(creator_id, filename)
            ugo.Items.append((
                "button", 
                3, 
                "", 
                f"http://flipnote.hatena.com/ds/v2-xx/movie/{creator_id}/{filename}.ppm",
                [star_count, "765", "573", "0"],
                (f"{filename}.ppm", tmb_data)
            ))
        
        # 6. Next Page Button
        if has_next:
            next_url = f"{base_url}/newmovies.uls?page={page_num + 1}"
            ugo.Items.append(("button", 115, "Next", next_url, ["", ""], None))
        
        return ugo.Pack()

    def handle_request(self, query_args, path, client_ip):
        """Endpoint handler to be called by your server router."""
        # Python 3 query_args are usually bytes or lists of strings
        try:
            page_idx = int(query_args.get("page", [1])[0]) - 1
        except (ValueError, IndexError):
            page_idx = 0

        with self.lock:
            if 0 <= page_idx < len(self.pages):
                Log(client_ip, f"{path} page {page_idx + 1}")
                return 200, self.pages[page_idx]
        
        return 404, b"Not Found"

# Global instance
manager = NewMoviesManager()

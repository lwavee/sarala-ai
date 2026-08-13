import subprocess
import webbrowser
import os

class ToolExecutor:
    def __init__(self):
        # We can expand this class later to include file operations and more
        pass

    def open_application(self, app_name: str) -> str:
        app_name = app_name.lower().strip()
        try:
            if app_name in ["browser", "web browser", "chrome", "edge"]:
                # Uses Python's built in webbrowser module for cross-platform compatibility
                webbrowser.open("http://www.google.com")
                return f"I have opened the {app_name} for you."
                
            elif app_name in ["notepad", "text editor", "editor"]:
                # Using a generic approach. In WSL, notepad.exe is often available.
                try:
                    subprocess.Popen(["notepad.exe"])
                    return "I have opened Notepad."
                except FileNotFoundError:
                    return "Notepad.exe not found on this system. Are you running pure Linux?"
                    
            elif "terminal" in app_name:
                return "I'm currently running in a terminal, so I'm already here!"
                
            else:
                return f"Sorry, I don't have a tool configured to open '{app_name}' right now."
                
        except Exception as e:
            return f"An error occurred while trying to open {app_name}: {str(e)}"

    def play_youtube(self, query: str) -> str:
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded_query}"
            webbrowser.open(url)
            return f"I have opened YouTube to play '{query}'."
        except Exception as e:
            return f"Failed to play on YouTube: {str(e)}"

    def search_google(self, query: str) -> str:
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded_query}"
            webbrowser.open(url)
            return f"I have searched for '{query}' on Google."
        except Exception as e:
            return f"Failed to search on Google: {str(e)}"

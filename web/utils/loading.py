from flask import jsonify
from functools import wraps

def create_loading_page(title, initial_content, nav_links=None, loading_container_id="content-container", api_endpoint=None):
    """
    Creates a page with immediate loading and async content loading.
    
    Args:
        title: Page title
        initial_content: Content to show immediately (e.g., user profile, guild info)
        nav_links: Navigation links for the page header
        loading_container_id: ID of the container that will be updated with async content
        api_endpoint: API endpoint to fetch the async content from
    """
    loading_script = ""
    if api_endpoint:
        loading_script = f"""
        <script>
          // Load content data asynchronously
          fetch('{api_endpoint}')
            .then(response => response.json())
            .then(data => {{
              if (data.error) {{
                document.getElementById('{loading_container_id}').innerHTML = 
                  '<div class="col-span-full text-center py-12"><p class="text-red-500 dark:text-red-400">' + data.error + '</p></div>';
                return;
              }}
              document.getElementById('{loading_container_id}').innerHTML = data.html;
            }})
            .catch(error => {{
              console.error('Error loading content:', error);
              document.getElementById('{loading_container_id}').innerHTML = 
                '<div class="col-span-full text-center py-12"><p class="text-red-500 dark:text-red-400">Failed to load content. Please refresh the page.</p></div>';
            }});
        </script>
        """
    
    return initial_content + loading_script

def create_loading_container(loading_text="Loading...", container_classes="grid md:grid-cols-2 lg:grid-cols-3 gap-6"):
    """
    Creates a loading container with spinner and text.
    
    Args:
        loading_text: Text to show while loading
        container_classes: CSS classes for the container
    """
    return f"""
    <div class="{container_classes}">
      <div class="col-span-full flex flex-col items-center justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-4"></div>
        <p class="text-gray-500 dark:text-gray-400">{loading_text}</p>
      </div>
    </div>
    """

def create_async_script(api_endpoint, container_id="content-container", callback_function=None):
    """
    Creates a JavaScript snippet for async loading.
    
    Args:
        api_endpoint: API endpoint to fetch data from
        container_id: ID of container to update
        callback_function: Optional JavaScript function name to call after loading
    """
    callback_call = f"if (typeof {callback_function} === 'function') {{ {callback_function}(); }}" if callback_function else ""
    
    return f"""
    <script>
      fetch('{api_endpoint}')
        .then(response => response.json())
        .then(data => {{
          if (data.error) {{
            document.getElementById('{container_id}').innerHTML = 
              '<div class="text-center py-12"><p class="text-red-500 dark:text-red-400">' + data.error + '</p></div>';
            return;
          }}
          document.getElementById('{container_id}').innerHTML = data.html;
          {callback_call}
        }})
        .catch(error => {{
          console.error('Error loading content:', error);
          document.getElementById('{container_id}').innerHTML = 
            '<div class="text-center py-12"><p class="text-red-500 dark:text-red-400">Failed to load content. Please refresh the page.</p></div>';
        }});
    </script>
    """

def async_route(api_endpoint):
    """
    Decorator to create async API routes that return JSON with HTML content.
    
    Usage:
        @async_route('/api/some-endpoint')
        def some_api_function():
            # Your async data loading logic here
            return some_html_content
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                html_content = func(*args, **kwargs)
                return jsonify({"html": html_content})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        return wrapper
    return decorator

def create_error_content(message="An error occurred"):
    """Creates standardized error content."""
    return f'<div class="col-span-full text-center py-12"><p class="text-red-500 dark:text-red-400">{message}</p></div>'

def create_empty_content(message="No items found"):
    """Creates standardized empty state content."""
    return f'<div class="col-span-full text-center py-12"><p class="text-gray-500 dark:text-gray-400">{message}</p></div>'

def create_loading_skeleton(count=3, card_class="bg-white dark:bg-gray-800 rounded-2xl shadow p-5", layout_type="centered"):
    """
    Creates skeleton loading cards.
    
    Args:
        count: Number of skeleton cards to create
        card_class: CSS classes for each skeleton card
        layout_type: "centered" for dashboard-style cards, "guild" for profile guild cards, "stats" for stats cards
    """
    skeleton_cards = ""
    for i in range(count):
        if layout_type == "guild":
            # Guild card layout with icon + text side by side
            skeleton_content = """
            <div class="animate-pulse">
              <!-- Guild icon placeholder -->
              <div class="flex items-center gap-4 mb-4">
                <div class="bg-gray-200 dark:bg-gray-600 h-16 w-16 rounded-full"></div>
                <div class="flex-1">
                  <div class="bg-gray-200 dark:bg-gray-600 h-5 w-32 rounded mb-2"></div>
                  <div class="bg-gray-200 dark:bg-gray-600 h-3 w-24 rounded mb-1"></div>
                  <div class="bg-gray-200 dark:bg-gray-600 h-3 w-20 rounded"></div>
                </div>
              </div>
              <div class="bg-gray-200 dark:bg-gray-600 h-8 rounded"></div>
            </div>
            """
        elif layout_type == "stats":
            # Stats card layout with title, number, and description
            skeleton_content = """
            <div class="animate-pulse">
              <div class="bg-gray-200 dark:bg-gray-600 h-5 w-30 rounded mb-2"></div>
              <div class="bg-gray-200 dark:bg-gray-600 h-8 w-20 rounded mb-2"></div>
              <div class="bg-gray-200 dark:bg-gray-600 h-4 w-40 rounded"></div>
            </div>
            """
        else:
            # Centered layout for dashboard cards
            skeleton_content = """
            <div class="animate-pulse">
              <div class="bg-gray-200 dark:bg-gray-600 h-20 w-20 rounded-full mx-auto mb-3"></div>
              <div class="bg-gray-200 dark:bg-gray-600 h-4 w-40 rounded mb-2 mx-auto"></div>
              <div class="bg-gray-200 dark:bg-gray-600 h-3 rounded w-3/4 mx-auto mb-4"></div>
              <div class="bg-gray-200 dark:bg-gray-600 h-8 rounded"></div>
            </div>
            """
        
        skeleton_cards += f"""
        <div class="{card_class}">
          {skeleton_content}
        </div>
        """
    return skeleton_cards
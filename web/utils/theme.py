def get_theme_html_head(page_title="Dashboard", favicon_url="https://cdn.discordapp.com/avatars/732422232273584198/624035e5e9a841bfd3020e35a0a5c0a0.png?size=1024"):
    """
    Returns the HTML head section with dark mode functionality
    """
    return f"""
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>{page_title}</title>
      <link rel="icon" type="image/png" href="{favicon_url}">
      
      <!-- OG -->
      <meta property="og:url" content="https://fischl.app">
      <meta property="og:site_name" content="Fischl">
      <!-- descriptions -->
      <meta property="og:description"
         content="Fischl is a multi-purpose Genshin-based verified Discord bot that includes customizable ticket system, co-op matchmaking, chat minigames, partnership system, and more 👀">
      <meta name="description"
         content="Fischl is a multi-purpose Genshin-based verified Discord bot that includes customizable ticket system, co-op matchmaking, chat minigames, partnership system, and more 👀">
      <!-- end descriptions -->
      <meta property="og:title" content="Invite Fischl - A Simple & Powerful Utility Discord Bot">
      <!-- embed message second line big text title -->
      <meta property="og:image" content="https://cdn.discordapp.com/avatars/732422232273584198/624035e5e9a841bfd3020e35a0a5c0a0.png">
      <!-- embed message image -->
      <meta name="theme-color" content="#bd40e3"> <!-- embed message side color -->
      
      <script src="https://cdn.tailwindcss.com"></script>
      <script>
        tailwind.config = {{
          darkMode: 'class',
          theme: {{
            extend: {{
              spacing: {{
                'safe-top': 'env(safe-area-inset-top)',
                'safe-bottom': 'env(safe-area-inset-bottom)',
                'safe-left': 'env(safe-area-inset-left)',
                'safe-right': 'env(safe-area-inset-right)',
              }}
            }}
          }}
        }}
      </script>
      <style>
        /* Custom scrollbar styles for webkit browsers */
        ::-webkit-scrollbar {{
          width: 8px;
          height: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
          background: transparent;
        }}
        
        ::-webkit-scrollbar-thumb {{
          background: rgba(156, 163, 175, 0.5);
          border-radius: 4px;
          border: none;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
          background: rgba(156, 163, 175, 0.7);
        }}
        
        /* Dark mode scrollbar */
        .dark ::-webkit-scrollbar-thumb {{
          background: rgba(75, 85, 99, 0.5);
        }}
        
        .dark ::-webkit-scrollbar-thumb:hover {{
          background: rgba(75, 85, 99, 0.7);
        }}
        
        ::-webkit-scrollbar-corner {{
          background: transparent;
        }}
        
        /* For Firefox */
        * {{
          scrollbar-width: thin;
          scrollbar-color: rgba(156, 163, 175, 0.5) transparent;
        }}
        
        .dark * {{
          scrollbar-color: rgba(75, 85, 99, 0.5) transparent;
        }}
      </style>
      <script>
        // Check for saved theme preference or default to 'light' mode
        const theme = localStorage.getItem('theme') || 
                     (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        
        if (theme === 'dark') {{
          document.documentElement.classList.add('dark');
        }}
      </script>
    </head>"""


def get_dark_mode_button():
    """
    Returns the HTML for the dark mode toggle button with improved mobile accessibility
    """
    return """
          <button onclick="toggleDarkMode()" 
                  class="p-3 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors touch-manipulation min-w-[44px] min-h-[44px] flex items-center justify-center"
                  aria-label="Toggle dark mode">
            <svg class="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path class="dark:hidden" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>
              <path class="hidden dark:block" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path>
            </svg>
          </button>"""


def get_navbar(title, nav_links=None, show_dark_mode_button=True):
    """
    Returns a complete mobile-responsive navbar with hamburger menu, optional dark mode button and navigation links
    
    Args:
        title (str): The title to display in the navbar
        nav_links (list): List of tuples with (url, text, css_classes)
        show_dark_mode_button (bool): Whether to show the dark mode toggle button
    """
    if nav_links is None:
        nav_links = []
    
    dark_mode_btn = get_dark_mode_button() if show_dark_mode_button else ""
    
    # Desktop navigation items
    desktop_nav_items = ""
    mobile_nav_items = ""
    
    for url, text, css_classes in nav_links:
        desktop_nav_items += f'<a href="{url}" class="{css_classes} hidden md:block px-3 py-2 rounded-md text-sm font-medium transition-colors">{text}</a>'
        mobile_nav_items += f'<a href="{url}" class="{css_classes} block px-3 py-2 rounded-md text-base font-medium transition-colors">{text}</a>'
    
    return f"""
      <nav class="bg-white dark:bg-gray-800 shadow transition-colors">
        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div class="flex h-16 items-center justify-between">
            <!-- Logo and title section -->
            <div class="flex items-center">
              <a href="https://fischl.app/dashboard" class="flex items-center">
                <img src="https://cdn.discordapp.com/avatars/732422232273584198/624035e5e9a841bfd3020e35a0a5c0a0.png?size=1024" 
                     alt="Fischl" 
                     class="h-8 w-8 sm:h-10 sm:w-10 rounded-full">
                <h1 class="ml-3 text-lg sm:text-xl font-bold text-gray-900 dark:text-white truncate">{title}</h1>
              </a>
            </div>
            
            <!-- Desktop navigation -->
            <div class="hidden md:flex items-center gap-4">
              {desktop_nav_items}
              {dark_mode_btn}
            </div>
            
            <!-- Mobile menu button -->
            <div class="flex items-center gap-2 md:hidden">
              {dark_mode_btn}
              <button id="mobile-menu-button" 
                      onclick="toggleMobileMenu()" 
                      class="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
                      aria-expanded="false"
                      aria-label="Toggle navigation menu">
                <svg class="w-6 h-6 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
              </button>
            </div>
          </div>
        </div>
        
        <!-- Mobile navigation menu -->
        <div id="mobile-menu" class="hidden md:hidden bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
          <div class="px-2 pt-2 pb-3 space-y-1">
            {mobile_nav_items}
          </div>
        </div>
      </nav>"""


def wrap_page(title, content, nav_links, favicon_url=None):
    """
    Wraps content in a complete HTML page with dark mode support and mobile-responsive design
    
    Args:
        title (str): Page title
        content (str): HTML content for the page body
        nav_links (list): Navigation links for the navbar
        favicon_url (str): Custom favicon URL (optional)
    """
    if favicon_url is None:
        favicon_url = "https://cdn.discordapp.com/avatars/732422232273584198/624035e5e9a841bfd3020e35a0a5c0a0.png?size=1024"
    
    nav_links.append(("/logout", "Logout", "text-red-500 dark:text-red-400 font-medium hover:text-red-700 dark:hover:text-red-300"))
    
    head = get_theme_html_head(title, favicon_url)
    navbar = get_navbar(title, nav_links) # or title.split(' - ')[0]
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    {head}
    <body class="bg-gray-100 dark:bg-gray-900 min-h-screen transition-colors">
      {navbar}
      <main class="container mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 max-w-7xl">
        <div class="min-h-[calc(100vh-200px)]">
          {content}
        </div>
      </main>
      
      <script>
        // Enhanced dark mode toggle function
        function toggleDarkMode() {{
          try {{
            console.log('Dark mode toggle clicked');
            const html = document.documentElement;
            const isDark = html.classList.contains('dark');
            
            if (isDark) {{
              html.classList.remove('dark');
              localStorage.setItem('theme', 'light');
              console.log('Switched to light mode');
            }} else {{
              html.classList.add('dark');
              localStorage.setItem('theme', 'dark');
              console.log('Switched to dark mode');
            }}
          }} catch (error) {{
            console.error('Error toggling dark mode:', error);
          }}
        }}
        
        // Enhanced mobile menu toggle function
        function toggleMobileMenu() {{
          try {{
            console.log('Mobile menu toggle clicked');
            const mobileMenu = document.getElementById('mobile-menu');
            const menuButton = document.getElementById('mobile-menu-button');
            
            if (!mobileMenu || !menuButton) {{
              console.warn('Mobile menu elements not found');
              return;
            }}
            
            const isHidden = mobileMenu.classList.contains('hidden');
            console.log('Menu currently hidden:', isHidden);
            
            if (isHidden) {{
              mobileMenu.classList.remove('hidden');
              menuButton.setAttribute('aria-expanded', 'true');
              console.log('Menu opened');
            }} else {{
              mobileMenu.classList.add('hidden');
              menuButton.setAttribute('aria-expanded', 'false');
              console.log('Menu closed');
            }}
          }} catch (error) {{
            console.error('Error toggling mobile menu:', error);
          }}
        }}
        
        // Setup after DOM loads
        document.addEventListener('DOMContentLoaded', function() {{
          console.log('DOM loaded, setting up event listeners');
          
          // Close mobile menu when clicking outside
          document.addEventListener('click', function(event) {{
            try {{
              const mobileMenu = document.getElementById('mobile-menu');
              const menuButton = document.getElementById('mobile-menu-button');
              
              if (mobileMenu && menuButton && 
                  !mobileMenu.contains(event.target) && 
                  !menuButton.contains(event.target)) {{
                mobileMenu.classList.add('hidden');
                menuButton.setAttribute('aria-expanded', 'false');
              }}
            }} catch (error) {{
              console.error('Error handling outside click:', error);
            }}
          }});
          
          console.log('Event listeners setup complete');
        }});
        
        // Make functions globally available
        window.toggleDarkMode = toggleDarkMode;
        window.toggleMobileMenu = toggleMobileMenu;
      </script>
      </script>
    </body>
    </html>"""


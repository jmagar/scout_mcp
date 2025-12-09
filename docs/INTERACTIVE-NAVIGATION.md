# Interactive Directory Navigation

The Scout MCP server now includes fully interactive directory navigation using MCP-UI's tool call messaging system.

## Features

### 🖱️ Click-to-Navigate
- **Click on any folder** to navigate into it
- **Click on any file** to view its contents
- Each row in the directory listing is clickable and will trigger a new `scout` tool call

### 🧭 Breadcrumb Navigation
- **Clickable path segments** showing your current location
- Click any parent folder in the breadcrumb to jump directly to it
- Home icon (🏠) to return to root directory

### ⬆️ Parent Directory Button
- Quick access button to navigate up one level
- Located in the search bar for easy access

### 🔍 Real-time Filtering
- Filter files and folders as you type
- Instant search without triggering navigation

## How It Works

### MCP-UI Tool Calls

When you click on a file or folder, the UI sends a `window.parent.postMessage` to the MCP client:

```javascript
window.parent.postMessage({
    type: 'tool',
    payload: {
        toolName: 'scout',
        params: {
            target: 'hostname:/path/to/item'
        }
    }
}, '*');
```

The MCP client receives this message and automatically invokes the `scout` tool with the new target path, creating a seamless navigation experience.

## Design

### shadcn/ui Inspired Styling

The UI is styled to match shadcn/ui's design system:

- **CSS Variables**: Using HSL color tokens for consistency
- **Typography**: Inter/System fonts with proper letter spacing
- **Transitions**: Smooth 150ms transitions on interactive elements
- **Shadows**: Subtle elevation with box-shadows
- **Radius**: Consistent 0.5rem border radius
- **Hover States**: Clear feedback on clickable elements

### Color System

```css
--primary: 221.2 83.2% 53.3%;      /* Blue primary actions */
--secondary: 210 40% 96.1%;         /* Gray secondary actions */
--muted: 210 40% 96.1%;            /* Subtle backgrounds */
--border: 214.3 31.8% 91.4%;       /* Dividers and borders */
--accent: 210 40% 96.1%;           /* Hover states */
```

## File Types Supported

The interactive UI works for:
- ✅ Directories (clickable folder icons)
- ✅ Files (clickable file icons)
- ✅ Symlinks (follow to target)

## Browser Compatibility

Requires:
- `window.parent.postMessage` API
- CSS custom properties (variables)
- Modern JavaScript (ES6+)

Tested with:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Example Usage

```bash
# Navigate to a directory
scout("myserver:/var/www")

# Click on "html" folder in UI → triggers:
# scout("myserver:/var/www/html")

# Click breadcrumb "www" → triggers:
# scout("myserver:/var/www")

# Click "Parent Directory" button → triggers:
# scout("myserver:/var")
```

## Implementation Details

### Files Modified
- `scout_mcp/ui/templates.py` - Added navigation JavaScript and shadcn styling
- `scout_mcp/ui/generators.py` - No changes needed (uses templates)

### Key Functions
- `navigateToPath(host, path, isDir)` - Sends tool call message
- `navigateToParent()` - Navigates up one directory level
- `filterEntries()` - Client-side search filtering

### URI Format
All navigation uses the standard scout target format:
```
hostname:/absolute/path
```

## Limitations

1. **MCP-UI Client Required**: Standard MCP clients won't show the interactive UI
2. **No React Components**: Uses vanilla HTML/CSS/JS (no shadcn React components)
3. **Single Host Per View**: Cannot switch hosts from within the UI
4. **Text-Based Icons**: Uses emoji icons instead of icon libraries

## Future Enhancements

Potential improvements:
- [ ] Sort columns by name/size/date
- [ ] Multi-file selection with checkboxes
- [ ] Keyboard navigation (arrow keys)
- [ ] File context menu (right-click)
- [ ] Directory size calculation
- [ ] Favorite/bookmark directories
- [ ] Recent locations history
- [ ] File preview panel

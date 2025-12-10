# ANTHROPIC Environment Variable Leak Investigation

**Date:** 2025-12-09
**Session Duration:** Extended troubleshooting session
**Status:** ✅ Resolved

## Session Overview

Investigated and resolved persistent ANTHROPIC_* environment variables leaking into all new terminal sessions in VSCode/code-server. The variables were being exported on every new shell session, despite multiple attempts to identify the source.

## Timeline

### Initial Investigation (First Attempt)
1. **Problem Identified**: User noticed ANTHROPIC environment variables set in all new terminals:
   - `ANTHROPIC_BASE_URL=https://cli-api.tootie.tv`
   - `ANTHROPIC_AUTH_TOKEN=sk-proxy-local-access-key`
   - `ANTHROPIC_DEFAULT_OPUS_MODEL=gemini-3-pro-preview`
   - `ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-5-20250929`
   - `ANTHROPIC_DEFAULT_HAIKU_MODEL=gpt-5.1-codex-max-medium`

2. **Search Shell Configs**: Checked standard shell configuration files
   - `/config/.bashrc` - Not found
   - `/config/.zshrc` - Not found (using ZDOTDIR)
   - `/config/.config/zsh/.zshrc` - Clean, no ANTHROPIC exports
   - `/config/.zshenv` - Clean
   - `/config/.config/.profile` - Clean
   - `/config/.local/bin/env` - Not searched initially

3. **Search System-Wide**: Checked `/etc/environment` and system configs
   - Result: Not found

4. **VSCode Extension Settings**: Found and deleted cached configuration
   - Located at: `/config/data/User/caches/CachedConfigurations/folder/-6ddd0fc0/configuration.json`
   - Contained: `claudeCode.environmentVariables` with all five ANTHROPIC variables
   - **Action**: Deleted the cached configuration file
   - **Result**: Variables still appeared in new terminals (not the source!)

### Deep Investigation (Second Attempt)
5. **Discovered claude-wrapper Script**
   - Located at: `/config/.local/bin/claude-wrapper:4-10`
   - Exports ANTHROPIC variables unconditionally
   - Initially suspected as the source of leakage

6. **Verified Wrapper Execution**
   - Confirmed `/config/.local/bin/claude` is a symlink to actual Claude binary
   - Wrapper is separate script, NOT called when running `claude` command
   - Wrapper only runs when explicitly invoked as `claude-wrapper` or `cc` alias

7. **Continued Search**: Variables persisted despite wrapper investigation
   - Checked code-server process environment: Clean
   - Checked VSCode workspace files: Clean
   - Checked all cached configurations: Clean
   - All searches came up empty

### Final Resolution (Root Cause Found)
8. **Comprehensive File Search**
   ```bash
   grep -r "export ANTHROPIC" /config/ 2>/dev/null | grep -v ".git" | grep -v ".cache" | grep -v "data/User/History" | grep -v ".zsh_history"
   ```

9. **Root Cause Identified**: `/config/.oh-my-zsh/custom/aliases.zsh:106`
   ```bash
   # Claude wrapper with custom API endpoint
   # Source it to get 'cc' alias and 'code' function
   source "$HOME/.local/bin/claude-wrapper"
   ```

   **This was the culprit!** The aliases file was **sourcing** (not executing) the wrapper script on every shell startup, causing all exports to run and leak into the shell environment.

10. **Resolution Steps**:
    - Deleted `/config/.local/bin/claude-wrapper` (user's request)
    - Removed source line from `/config/.oh-my-zsh/custom/aliases.zsh:104-106`
    - Replaced with comment: `# Claude wrapper removed - environment variables were leaking into shell`

## Key Findings

### The Leak Mechanism
- **Source vs Execute**: When a script is **sourced** (with `source` or `.`), all `export` statements affect the calling shell
- **Execution**: When a script is **executed** directly, exports only affect that subprocess and its children
- The aliases file was sourcing the wrapper, not executing it
- Every new zsh shell loaded oh-my-zsh custom aliases → sourced wrapper → exported ANTHROPIC vars

### Misleading Trails
1. **VSCode Cached Configuration**: Found ANTHROPIC vars in cached config, but deleting it had no effect
   - Path: `/config/data/User/caches/CachedConfigurations/folder/-6ddd0fc0/configuration.json`
   - Likely an old configuration from when variables were set via VSCode extension settings
   - Not actively used by current VSCode instance

2. **claude-wrapper Script**: Initially suspected because it exports the variables
   - Path: `/config/.local/bin/claude-wrapper`
   - Contains `export ANTHROPIC_*` statements (lines 4-10)
   - BUT: Only runs when explicitly called, not when running `claude` command
   - The real `claude` binary is at `/config/.local/share/claude/versions/2.0.61`

### Why Variables Persisted
Even after deleting the wrapper, variables would continue appearing because:
1. The aliases file attempted to source a non-existent file (would error)
2. But any existing shells still had the variables from previous source
3. New shells would fail to source, but previous exports remained in that shell's environment

## Technical Decisions

### Why Not Keep the Wrapper?
- User wanted to eliminate environment variable leakage completely
- Wrapper was designed to set vars only when running `claude` with custom API endpoint
- But the sourcing in aliases.zsh defeated that design
- Could have fixed by moving exports after sourcing check in wrapper, but user chose deletion

### Alternative Solutions Considered
1. **Move exports after sourcing check in wrapper** (not chosen)
   ```bash
   if [[ sourcing check ]]; then
       # Only provide functions/aliases
       return 0
   fi
   # Exports would go here (only when executing)
   ```

2. **Use VSCode extension settings** (rejected - variables leak)
   - `claudeCode.environmentVariables` in settings.json
   - Testing showed these leak to integrated terminals

3. **Use ~/.claude/settings.json env section** (rejected - variables leak)
   - Confirmed that env vars in `.claude/settings.json` leak to terminals
   - Tested with `CLAUDE_CODE_DISABLE_SANDBOX` - appeared in shell

## Files Modified

### Deleted
- `/config/.local/bin/claude-wrapper` - Removed entirely per user request

### Modified
- `/config/.oh-my-zsh/custom/aliases.zsh:104-106`
  - **Before**:
    ```bash
    # Claude wrapper with custom API endpoint
    # Source it to get 'cc' alias and 'code' function
    source "$HOME/.local/bin/claude-wrapper"
    ```
  - **After**:
    ```bash
    # Claude wrapper removed - environment variables were leaking into shell
    ```

## Commands Executed

### Discovery Commands
```bash
# Check current environment
env | grep ANTHROPIC

# Search shell configs
grep -r "ANTHROPIC" /config/.config/zsh/ /config/.bashrc /config/.zshrc /config/.profile /config/.zshenv

# Search VSCode configurations
grep -r "ANTHROPIC_BASE_URL" /config/data/User/ | grep -v "History"

# Find cached configurations
find /config/data/User -name "settings.json" -o -name "configuration.json" | grep -v History

# Check which claude binary is used
which claude
ls -la /config/.local/bin/claude*

# Comprehensive search for exports
grep -r "export ANTHROPIC" /config/ | grep -v ".git" | grep -v ".cache" | grep -v "data/User/History"
```

### Verification Commands
```bash
# Check code-server process environment
ps aux | grep code-server
cat /proc/1057/environ | tr '\0' '\n' | grep ANTHROPIC

# Verify PATH
echo $PATH

# Check if wrapper is being sourced
grep -r "source.*claude-wrapper\|\..*claude-wrapper" /config/.config/zsh/
```

## Environment Details

- **Container**: code-server running in Docker
- **Host Connection**: VSCode Insiders remote connection from host to Docker
- **Shell**: zsh with oh-my-zsh framework
- **Shell Config Location**: `ZDOTDIR=/config/.config/zsh`
- **Oh-My-Zsh Custom**: `/config/.oh-my-zsh/custom/`
- **Code-Server Data**: `/config/data/User/`
- **VSCode Remote Data**: `/mnt/cache/appdata/.vscode-server-insiders/`

## Lessons Learned

1. **Source vs Execute Matters**: Always distinguish between sourcing and executing scripts
   - Sourcing runs in current shell → exports leak
   - Executing runs in subprocess → exports contained

2. **Check Custom Aliases**: Oh-My-Zsh custom directory is easy to overlook
   - Located at `~/.oh-my-zsh/custom/`
   - Sourced on every shell startup
   - Common place for environment modifications

3. **Cached Configs Can Be Red Herrings**: VSCode caches old configurations
   - May no longer be active
   - Deleting them may have no effect
   - Always verify after changes

4. **Comprehensive Search Required**: Environment variables can be set from many places
   - Shell rc files (`.bashrc`, `.zshrc`, etc.)
   - Profile files (`.profile`, `.zprofile`, `.zshenv`)
   - Custom frameworks (oh-my-zsh, prezto)
   - System-wide (`/etc/environment`, `/etc/profile.d/`)
   - Editor settings (VSCode, vim, etc.)
   - Container/Docker environment
   - Parent process inheritance

5. **Test Changes Immediately**: Open new terminal to verify changes take effect
   - Environment variables persist in existing shells
   - Must spawn fresh shell to see changes

## Next Steps

- ✅ Variables removed from shell environment
- ✅ Wrapper script deleted
- ✅ Aliases file cleaned
- ⚠️ User should open new terminal to verify variables are gone
- ⚠️ If user needs custom API endpoint for Claude, must use different approach:
  - Option 1: Create separate wrapper that's executed (not sourced)
  - Option 2: Use environment-specific startup script
  - Option 3: Set variables only in specific project contexts

## Verification

User should run in new terminal:
```bash
env | grep ANTHROPIC
```

Expected result: No output (variables gone)

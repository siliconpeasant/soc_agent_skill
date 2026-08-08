# MCP registration

Agent Skills installation and MCP registration are separate operations. The open Skill format does not define a universal MCP configuration location, so use the bundled helper to register through supported Agent CLIs or emit portable JSON.

Run commands from the installed `wavedrom-gen` directory after `npm ci --omit=dev`.

## Codex

```text
node scripts/register-mcp.mjs --agent codex
```

The helper invokes `codex mcp add wavedrom-gen -- node <absolute-server-path> --stdio`. Codex stores the registration in its user configuration.

## Claude Code

```text
node scripts/register-mcp.mjs --agent claude-code --scope user
```

Allowed Claude Code scopes are `local`, `project`, and `user`. On native Windows the registered command is `node`, so the `cmd /c` workaround required for `npx` servers is unnecessary.

## Other MCP clients

```text
node scripts/register-mcp.mjs --agent generic
```

Copy the emitted `mcpServers.wavedrom-gen` object into the client's MCP configuration. It contains the current Node executable and absolute server path, so it does not depend on the working directory.

## Safety

- Add `--dry-run` to print the native command without changing configuration.
- The helper refuses to replace an existing registration by default.
- Add `--force` only when replacement is intentional; it removes the named registration before adding the new one.

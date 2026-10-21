# Alexa+ add-on package (prepared, not deployed)

This folder holds the `addon.json` manifest that the Alexa AI CLI
(`alexa-ai new mcp` / `alexa-ai deploy`) uses to register an MCP server as an
Alexa+ add-on.

**It has not been deployed.** Amazon's Alexa+ add-on tooling (Category SDK,
MCP Toolkit, CLI, and Web Simulator) is a preview limited to select partners,
and the hackathon FAQ confirms participants cannot get access. The manifest is
included to show the server is ready for real onboarding once access exists.
For the hackathon, Sous is demonstrated through the web simulator in
`simulator/`, which acts as a real MCP client.

## What is ready

- `addon.json`: store listing, example phrases, policy links, media assets,
  and the MCP endpoint.
- Media assets in `docs/assets/`: all six light-icon sizes (64 to 241 px) and
  a 600x900 carousel image. Regenerate with `python tools/generate_assets.py`.
- Privacy policy and terms of use in `docs/`, served by GitHub Pages.

## Steps once tooling access is available

1. Enable GitHub Pages for this repository with the `docs/` folder as source.
2. Replace `REPLACE_WITH_YOUR_GITHUB_USERNAME` with your GitHub username.
3. Deploy `server.py` behind a public HTTPS URL and replace
   `REPLACE_WITH_YOUR_PUBLIC_MCP_SERVER_URL`.
4. Run `alexa-ai configure`, then `alexa-ai deploy`.

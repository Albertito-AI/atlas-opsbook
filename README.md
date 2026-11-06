# Atlas Opsbook

Teach a coding agent to write and revise its own project operations manual. When a run exposes a mistake, the agent records what happened, writes an instruction, and tests where it should apply. The next session reads the accepted instruction before it starts work.

[Try the interactive casebook](https://www.alberttansinhon.com/atlas-opsbook/) · [Read the design paper](docs/WHITEPAPER.md) · [Inspect the pstack integration](docs/PSTACK.md)

## Try it in one minute

With Git and Python 3.9 or later:

```sh
git clone https://github.com/Albertito-AI/atlas-opsbook.git
cd atlas-opsbook
python3 opsbook.py demo
python3 examples/package_trial.py
```

The first command after cloning runs an offline teaching exercise. A draft requires a clean installation for every release. Replay finds the mistake: a documentation release has nothing to install. The learner then infers the narrower condition from practice cases. It prescribes the check when shipping a package and leaves a read-only inspection alone. The demo promotes that rule, uses it in a new task and restores the previous manual.

The second exercise builds a deliberately broken Python archive. The empty manual lets it through. The learned manual invokes a real isolated Python import, which fails on the broken archive and passes after the module is restored. Both exercises use temporary directories and need no account or model key.

## Give an agent its own manual

```sh
python3 install_agent.py codex /path/to/your/project
```

Choose `codex`, `cursor` or `claude`. The installer adds project instructions to the host's normal project file, copies the local CLI and initialises a project-specific SQLite manual. Existing Codex instructions are retained. Running the same installer twice is safe. Review the changes before committing them. Each checkout keeps its own local history by default.

Then ask the agent:

> Read your project manual before you begin. After this task, identify one mistake worth preventing. Record the incident and a counterexample. Write a rule in your own words, test it on separately labelled cases, and show me what the next session will do differently.

Use the [operator guide](docs/OPERATING.md) to supply evidence, inspect proposals and bind a rule to an actual check. The current engine learns bounded conditions for required checks. It persists procedures outside the model. A rule entering the manual conveys no additional authority.

## Use the full pstack workflow

Atlas Opsbook works alongside Lauren Tan's **pstack**. Use native pstack for routing, investigation, design, parallel work, verification and shipping. Opsbook supplies project-specific instructions before a task and tests new instructions after it. Its lock records the complete upstream plugin at a named commit, with **58 skills, 23 playbooks, two agent definitions and one automation pack**. Some upstream steps need Cursor, external tools or a configured model.

```sh
python3 pstack.py list
python3 pstack.py fetch
python3 pstack.py show playbook bug-fix
```

The catalogue is offline. Fetching the pinned source needs Git and network access. [Installation and host differences](docs/PSTACK.md).

## Release evidence

Version **0.1.0**, public alpha. Run `python3 -m unittest discover -s tests -v` for local regression tests. The [verification record](docs/VERIFICATION.md) separates software results, illustrative cases and open research questions. A comparative productivity or model-quality multiplier would require matched live-agent trials.

Original Opsbook code is released under the [MIT licence](LICENSE). The separately fetched pstack distribution retains Lauren Tan's upstream licence and attribution.

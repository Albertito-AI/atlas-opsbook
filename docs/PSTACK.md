# Using Atlas Opsbook with pstack

Lauren Tan's [original pstack distribution at the reference commit](https://github.com/cursor/plugins/tree/2776ddd2355d6d6c8747d3964600f28daf62f049/pstack) supplies the engineering skills, playbooks, agents, automation and documentation. The [inventory](../upstream.lock.json) was read from its Git tree rather than a marketplace summary. Tree `4719e1c4b4c43bac85d4206a8b41dd2899769c1c` identifies the complete pstack directory.

| Work | Entry point | Who executes it |
| --- | --- | --- |
| Configure models, route and run engineering work | `setup-pstack`, `poteto-mode`, its 23 playbooks | Native upstream plugin and host |
| Investigate, design, compare approaches, test and review | `how`, `why`, `architect`, `arena`, `interrogate`, `tdd` and other catalogue entries | Native upstream plugin and configured tools |
| Recall, reflect, create a personal mode or evaluate prompts | `recall`, `reflect`, `automate-me`, the eval playbook | Native upstream plugin |
| Coordinate agents, watch reviews or ship a stack | Host-specific playbooks and optional Benny automation | Native upstream plugin, model and authorised external services |
| Select project checks at task intake | `brief` and an installed project instruction | Opsbook and the host agent |
| Author, infer, test, promote or restore a local rule | `propose`, `learn`, `evaluate`, `promote`, `rollback` | Opsbook |
| Execute a bound local check | `verify` with an operator-supplied command file | Local subprocess |

In Cursor, run `/add-plugin pstack` followed by `/setup-pstack`. Use `/poteto-mode` for engineering work. In Claude Code, use `/plugin marketplace add cursor/plugins`, then `/plugin install pstack@cursor-plugins`. Upstream's [Claude host notes](https://github.com/cursor/plugins/blob/2776ddd2355d6d6c8747d3964600f28daf62f049/pstack/docs/harness/claude-code.md) explain command names and unsupported features. A normal marketplace install can advance beyond our reference commit. Use the pinned checkout for controlled comparisons.

For Codex, install the Opsbook project instructions and read individual original playbooks with `pstack.py show`. Codex can execute steps for which it has equivalent tools. Cursor-only features and the upstream agent orchestration require their original host. In all hosts, Opsbook's own manual works offline.

```sh
python3 pstack.py fetch
python3 pstack.py verify
python3 tests/check_upstream.py
python3 pstack.py show skill reflect
python3 pstack.py show playbook autonomous-run
python3 pstack.py show automation benny
```

The optional fetch creates a sparse checkout under `.opsbook/upstream`. The reader uses Git objects from the locked commit. It can read every indexed skill and playbook without relying on an edited working file. The complete upstream pstack directory includes supporting references, scripts, assets and its own MIT licence. The Benny pack requires Cursor Automations. Upstream identifies optional dependencies such as cursor-team-kit for certain UI and CLI steps. An account or separately supplied integration may be required for live execution.

The install and replay tests establish the Opsbook interfaces. A catalogue and complete source distribution cannot establish that every external model, watcher or host integration has run successfully.

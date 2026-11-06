# The first rule learned from the launch itself

Version 0.1.0's combined archive was readable and passed a ZIP integrity test. Its packaging code nevertheless discarded executable modes. A watcher can have the right contents and still fail when invoked directly after extraction. The original upstream checkout retained the correct modes.

The publishing agent wrote [this rule](rule.json) after inspecting the real defect. Its [case record](cases.json) identifies the incident and labels the synthetic comparisons explicitly. Install a disposable manual, record the cases, propose the rule, evaluate the returned proposal and promote it. The resulting [manual](MANUAL.md) is the actual output of the CLI.

```sh
python3 opsbook.py init
python3 opsbook.py record examples/launch-lesson/cases.json
python3 opsbook.py propose examples/launch-lesson/rule.json
# Substitute the proposal ID printed above.
python3 opsbook.py evaluate ID
python3 opsbook.py promote ID
python3 opsbook.py manual
```

In version 0.1.1 the packer preserves the upstream modes and reconstructs the Git tree from the finished ZIP for both pstack and its Claude adapter. Release publication depends on those checks. The revised test also exercises a byte-identical script archived without its executable bit and verifies that the alteration is rejected. This is one observed correction followed by a change to the release procedure. Evidence of general improvement would require independent trials.

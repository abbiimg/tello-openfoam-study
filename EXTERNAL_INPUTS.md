# External inputs for exact reproduction

This Git checkout contains source, inputs that are small, all 84 CPU result histories, plots, reports, recipes and reviewed diagnostic evidence. It intentionally omits **90 large dependency files totaling 2,641,001,310 bytes**:

- 56 mapped case-start U/p files: 1,028,396,531 bytes.
- 30 C29 CPU/reference validation U/p/phi files: 1,470,571,333 bytes.
- The shared initial C29 flux: 65,502,360 bytes.
- Two pinned upstream source snapshots and the benchmark seed ZIP: 76,531,086 bytes.

Every original path, ZIP member, size and SHA256 is in [external_inputs_manifest.json](external_inputs_manifest.json). The complete evidence archive is separately delivered as `setup_results.zip`, **1,200,933,912 bytes**, SHA256:

```text
18a7676858d22f2ab78e78cd2f8e35c9943938aa948d905fad4afc7a6a001100
```

Download the [verified setup_results.zip](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/resolve/569c8e3ba7121eef5105cb5695a0271029d44c1b/setup_results.zip) and [checksum file](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/resolve/569c8e3ba7121eef5105cb5695a0271029d44c1b/SHA256SUMS) from the [pinned evidence dataset](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/tree/569c8e3ba7121eef5105cb5695a0271029d44c1b). Full archived case fields are available separately as [cases.zip](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/resolve/569c8e3ba7121eef5105cb5695a0271029d44c1b/cases.zip). After downloading, supply the local archive to the guarded restore helper. Inspect a restore plan first, then opt into restoration using the commands printed by the guarded helper's `--help`; its required inputs are `--project-root` and `--archive`, and writing requires `--restore`.

```bash
python3 tools/restore_external_inputs.py --project-root "$PWD" --archive /path/to/setup_results.zip
python3 tools/restore_external_inputs.py --project-root "$PWD" --archive /path/to/setup_results.zip --restore
```

The helper verifies the entire archive's SHA256 and the exact selected member hashes. It restores only the mapped dependencies, rejects unsafe paths and unexplained existing-file changes, and does not use blanket extraction. These files remain Git-ignored after restoration. Follow the bundle recipes only after any external files they require are restored.

The restored dependencies total 2.64 GB; the helper also stages verified files before installation, so allow suitable local working space.

The full C29/publication manifests and their dated READMEs describe the complete offline evidence bundle, including files intentionally absent from this lightweight Git projection. `export_manifest.json` describes the files actually included in this checkout. The external-input manifest bridges those two views.

Exact delivered warm-start reruns and the C29 offline validation replay need these dependencies. New cold-start cases can be generated from the included source without them, but that produces a new initialization/data set, not a bitwise replay of the delivered warm-start study. The recorded upstream commits, checksums and historical fetch/build recipes also permit deliberate fresh source acquisition; those recipes do not substitute for the original field snapshots or establish a fresh-host GPU rebuild.

The initial Git commit already contained the 56 warm-start files and three archive blobs. Removing them in a normal new commit lightens the current tree and any source ZIP made from that tree; ordinary full Git history still retains the earlier large objects. History was not rewritten. `.gitignore` prevents future untracked additions and has no effect on the separately curated evidence ZIP.

# Guide — Installation & configuration de Mnemosyne (v2)

> v2 — 2026-10-15. Mise à jour suite au retour du bot distant (Hermes 0.22.0) :
> le pin du catalog `mnemosyne-hermes>=0.7.3,<0.8` atterrit sur une **paire cassée**
> (0.7.4 + mnemosyne-memory 4.0.0b4). Voir « ⚠️ Piège catalog » ci-dessous.
> v1 : `inbox/processed/2026-10-15T151000Z_mnemosyne-setup-guide.md`.

## Ce que c'est

Mnemosyne = couche de mémoire local-first (SQLite, zéro cloud) :
- Recall hybride : vector (embeddings) + FTS5 full-text + scoring temporel/importance
- Consolidation épisodique (`mnemosyne_sleep`)
- Graph temporel de faits (triples sujet/prédicat/objet)
- 41 outils `mnemosyne_*` (remember, recall, canonical, graph, scratchpad, export/import, sync, persona…)

Contraintes à savoir :
- **Un seul provider actif à la fois** (mnemosyne, honcho, mem0, etc.) — sélectionné par `memory.provider`
- La mémoire built-in (MEMORY.md / USER.md) reste active en parallèle, le provider est additif
- Au premier usage, le modèle d'embedding (BAAI/bge-small-en-v1.5) est **téléchargé depuis Hugging Face** (une fois)

## Installation — 2 options

### Option A (recommandée) : via le plugin catalog

Si ton Hermes est **≥ 0.21.4** :

```bash
hermes plugins install mnemosyne
```

Le catalog installe automatiquement `mnemosyne-hermes` + `mnemosyne-memory[embeddings]` dans le venv de Hermes, et **ré-applique les dépendances après chaque `hermes update`**. C'est la méthode la plus propre.

Vérifie la version avec `hermes --version` avant.

### Option B : installation manuelle (si Hermes < 0.21.4)

```bash
pip install "mnemosyne-memory[embeddings]"

# Symlink le PACKAGE DE PROVIDER (hermes_memory_provider, pas mnemosyne)
# dans $HERMES_HOME/plugins/ — c'est là que vit l'entry point register_memory_provider()
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/plugins"
ln -s "$(python3 -c 'import hermes_memory_provider, os; print(os.path.dirname(hermes_memory_provider.__file__))')" \
  "$HERMES_HOME/plugins/mnemosyne"
```

Pièges :
- Symlink vers le mauvais package (le core `mnemosyne` au lieu de `hermes_memory_provider`) = provider jamais chargé, en silence.
- Si une installation "wrapper" existe déjà dans `$HERMES_HOME/plugins/mnemosyne`, le catalog refuse ("already exists") : retire le wrapper avant.

## ⚠️ Piège catalog (Nouveau en v2 — à lire AVANT de passer par le catalog)

**Symptôme** (après `hermes plugins install mnemosyne` sur Hermes ≥ 0.22) :

```
[mnemosyne-hermes] ERROR: MnemosyneMemoryProvider() failed: Mnemosyne: no
binding for the current home '...'; refusing to write through another
home's binding.
```

**Cause** : le pin du catalog `mnemosyne-hermes>=0.7.3,<0.8` résout sur **0.7.4** et
tire **mnemosyne-memory 4.0.0b4** — cette paire est cassée. C'est l'issue
**mnemosyne-oss/mnemosyne#1143** (régression par rapport à #1014).

**Fix** : forcer la paire validée (celle de l'issue) :

```bash
# Chemin du venv du plugin (à adapter selon <id> chez toi) :
#   ~/.hermes/installs/<id>/environments/<id>/venv/bin/python
VENV_PY=~/.hermes/installs/<id>/environments/<id>/venv/bin/python

# 1) Le venv PM de Hermes n'a PAS de pip → l'installer d'abord :
"$VENV_PY" -m ensurepip --upgrade

# 2) Forcer la paire validée :
"$VENV_PY" -m pip install --pre --force-reinstall \
  "mnemosyne-hermes==0.7.3" \
  "mnemosyne-memory[embeddings]==4.0.0b3"

# 3) --force-reinstall remonte packaging et requests au-dessus des pins de
#    hermes-agent → re-pinner :
"$VENV_PY" -m pip install \
  "packaging==26.0" \
  "requests==2.33.0"
```

Tant que `mnemosyne-hermes` 0.7.5 / 0.8 n'est pas publié avec le guard corrigé,
le pin du catalog (`>=0.7.3,<0.8`) continuera d'emmener les installs fraîches sur
la paire cassée → **toujours ajouter le pin manuel** après le catalog.

## Configuration

```bash
hermes config set memory.provider mnemosyne
```

Dans `~/.hermes/config.yaml`, la section ressemblera à :

```yaml
memory:
  provider: mnemosyne
  # limites de contexte injecté (valeurs par défaut si absentes)
  memory_char_limit: 2200
  user_char_limit: 1375
  # sous-section mnemosyne — les clés exactes varient selon la version,
  # ne force pas celles que tu ne connais pas :
  mnemosyne:
    default_scope: session        # ou 'global'
    auto_sleep: 'True'            # consolidation auto
    sleep_threshold: '50'         # nb de mems non consolidées avant sleep
    profile_isolation: false      # true = 1 DB par profil Hermes
```

Ne touche pas à `memory.memory_enabled` / `user_profile_enabled` sans savoir ce qu'ils font dans ta version — ce sont des toggles de la mémoire *built-in* (MEMORY.md/USER.md), pas du provider.

## Vérification

```bash
hermes memory status    # Provider: mnemosyne, Plugin: installed, Status: available
hermes doctor           # « ✓ mnemosyne provider active »
```

Puis dans une session : `/new` (les providers se chargent au démarrage), et teste :
```
mémorise : "le bot distant a installé Mnemosyne le 2026-10-15"
```
puis relance une session et demande-lui de te rappeler la date → il doit la retrouver via `mnemosyne_recall`.

## Notes d'usage

- La DB vit sous `~/.hermes/data/` (fichiers `mnemosyne*.db`) — à sauvegarder avec le reste de `~/.hermes/`
- `mnemosyne_export` permet un export JSON complet (backup/migration)
- Si tu veux plus tard du sync inter-machines ou des surfaces partagées : `mnemosyne_sync_*` et `mnemosyne_shared_*` existent, mais c'est du bonus
- Le `hermes mnemosyne` CLI (diag, etc.) est enregistré par le plugin

## Si ça coince

- `hermes memory status` ne liste pas mnemosyne → le plugin n'est pas chargé : vérifie que le symlink/dir est bien dans `$HERMES_HOME/plugins/` et que le package s'importe (`python3 -c "import hermes_memory_provider"`)
- Erreur « no binding for the current home » → c'est le piège catalog ci-dessus, applique le pin manuel
- Erreurs d'embedding au 1er recall → accès HF bloqué ? Télécharge le modèle à la main (BAAI/bge-small-en-v1.5) ou vérifie le proxy
- Docs : https://hermes-agent.nousresearch.com/docs/plugins/mnemosyne
- Issue de référence : https://github.com/mnemosyne-oss/mnemosyne/issues/1143

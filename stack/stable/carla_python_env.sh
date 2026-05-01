#!/usr/bin/env bash

simctl_prepare_carla_python_overlay() {
  local overlay_dir="$1"
  local user_site
  local user_carla_dir

  if [[ -z "${overlay_dir}" ]]; then
    return 0
  fi

  mkdir -p "${overlay_dir}"
  user_site="$(python3 - <<'PY'
import site
print(site.getusersitepackages())
PY
)"
  user_carla_dir="${user_site}/carla"
  if [[ -d "${user_carla_dir}" ]]; then
    ln -sfn "${user_carla_dir}" "${overlay_dir}/carla"
  fi
}

simctl_carla_pythonpath_entries() {
  local carla_root="$1"
  local overlay_dir="$2"
  local candidate

  if [[ -n "${overlay_dir}" ]]; then
    printf '%s\n' "${overlay_dir}"
  fi

  for candidate in \
    "${carla_root}/PythonAPI/carla/dist/carla-0.9.15-py3.10"*.egg \
    "${carla_root}/PythonAPI/carla/dist/carla-0.9.15-cp310"*.whl; do
    if [[ -e "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
    fi
  done

  if [[ -d "${carla_root}/PythonAPI" ]]; then
    printf '%s\n' "${carla_root}/PythonAPI"
  fi
}

simctl_join_colon() {
  local IFS=:
  printf '%s\n' "$*"
}

simctl_carla_pythonpath() {
  local carla_root="$1"
  local overlay_dir="$2"
  local entry
  local pythonpath=""

  while IFS= read -r entry; do
    if [[ -z "${entry}" ]]; then
      continue
    fi
    if [[ -z "${pythonpath}" ]]; then
      pythonpath="${entry}"
    else
      pythonpath="${pythonpath}:${entry}"
    fi
  done < <(simctl_carla_pythonpath_entries "${carla_root}" "${overlay_dir}")
  printf '%s\n' "${pythonpath}"
}

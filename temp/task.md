### 🚀 Важные улучшения

Здесь есть несколько моментов, которые стоит доработать, чтобы сделать систему еще более надежной и предсказуемой для пользователя.

1.  **Поведение `output_file` для относительных путей вверх (`../`)**
    *   **Проблема**: Текущая логика в `compose_agent` может привести к неожиданному поведению. Если `output_file` задан как `../custom/report.md`, `_resolve_path` правильно вычислит путь относительно `base_dir`. Однако, поскольку этот путь не будет абсолютным, он затем будет объединен с `output_dir`, что приведет к некорректному пути вроде `.../.prompt_scribe/composed_prompts/../custom/report.md`.
    *   **Предложение**: Изменить логику для более явного разделения. Путь, указанный в `output_file`, должен либо находиться внутри `output_dir` (если это просто имя файла), либо быть полностью независимым (если это путь).

    ```python
    # F:/Projects/prompt-scribe/src/promptscribe/composer.py L:276

    # ... (код до этого)
    output_file_name = agent_config.get('output_file')
    if output_file_name:
         output_file_name = self._substitute_variables(output_file_name, variables)
         
         # ПРЕДЛАГАЕМОЕ ИЗМЕНЕНИЕ
         # Проверяем, является ли это путем или просто именем файла
         if '/' in output_file_name or '\\' in output_file_name:
             # Если это путь, разрешаем его относительно base_dir и используем как есть
             output_file_path = self._resolve_path(output_file_name)
         else:
             # Если это просто имя, помещаем его в output_dir
             output_file_path = output_dir / output_file_name
    else:
        # Если не указано, генерируем из имени агента и помещаем в output_dir
        output_file_name = f"{agent_name}.md"
        output_file_path = output_dir / output_file_name

    output_file_path.parent.mkdir(parents=True, exist_ok=True) # Гарантируем, что директория существует
    output_file_path.write_text(final_prompt, encoding="utf-8")
    # ...
    ```
    *   **Обоснование**: Это изменение делает поведение системы абсолютно предсказуемым: простое имя — в `output_dir`, путь — используется как есть.

2.  **Обработка шагов в `_run_simple_assembly`**
    *   **Проблема**: Код `key, value = next(iter(step.items()))` корректно работает, только если в словаре шага ровно один ключ. Если пользователь по ошибке напишет в YAML так:
        ```yaml
        - content: "Some text"
          h2: "A title" # Этот ключ будет проигнорирован
        ```
      Это приведет к тихому игнорированию данных, что может быть очень сложно отладить.
    *   **Предложение**: Добавить проверку на количество ключей в шаге и предупреждать пользователя.

    ```python
    # F:/Projects/prompt-scribe/src/promptscribe/composer.py L:136
    
    # ...
    for step in assembly_steps:
        if not isinstance(step, dict) or not step: # Проверка, что это непустой словарь
            continue

        if len(step) > 1:
            ui.warning(f"Assembly step has multiple keys, only the first will be used: {list(step.keys())}")

        key, value = next(iter(step.items()))
    # ...
    ```    *   **Обоснование**: Это улучшает обратную связь для пользователя и предотвращает трудноуловимые ошибки из-за неправильной конфигурации.

---

### 💡 Мелкие предложения

1.  **Сделать `read_file_for_jinja` методом класса**
    *   **Наблюдение**: Функция `read_file_for_jinja` создается заново при каждом вызове `compose_agent` в режиме Jinja2.
    *   **Предложение**: Превратить ее в обычный метод класса `_read_file_for_jinja(self, path: str) -> str`, который будет просто вызывать `self._read_file_content(path)`. Затем в `compose_agent` передавать `env.globals['read_file'] = self._read_file_for_jinja`.
    *   **Обоснование**: Это немного чище с точки зрения стиля и производительности, так как функция не создается в цикле.

2.  **Уточнение Regex для переменных**
    *   **Наблюдение**: Regex `r'\${([^}]+)}'` очень гибкий, но может случайно захватить лишнее, если в тексте встретится незакрытая фигурная скобка.
    *   **Предложение**: Если имена переменных должны следовать стандартным соглашениям (буквы, цифры, `_`), можно сделать его более строгим: `r'\${([a-zA-Z0-9_]+)}'`.
    *   **Обоснование**: Это делает парсинг переменных более надежным и предотвращает неожиданные замены. Если же нужна поддержка сложных выражений внутри `${...}`, то текущий вариант оправдан.

3.  **Добавить комментарии, объясняющие "почему"**
    *   **Наблюдение**: Код хорошо структурирован, но почти не содержит комментариев.
    *   **Предложение**: Добавить несколько комментариев в ключевых местах, например, в `compose_agent`, чтобы объяснить, почему Jinja2 является режимом по умолчанию.
        ```python
        # F:/Projects/prompt-scribe/src/promptscribe/composer.py L:214
        # Determine mode: 'assembly' is explicit. If not present, we default to the more
        # powerful Jinja2 templating mode, which allows for greater flexibility.
        if 'assembly' in agent_config:
            # ...
        ```
    *   **Обоснование**: Это поможет будущим разработчикам быстрее понять архитектурные решения, стоящие за кодом.
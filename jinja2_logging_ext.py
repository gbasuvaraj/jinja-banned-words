"""
Jinja2 extension that logs template lifecycle events.

Events emitted (all at DEBUG level to logger "jinja2.lifecycle"):

  extension.init          — extension registered with an Environment
  template.parse.start    — source code about to be parsed into an AST
  template.token          — each lexed token (type + value) during parsing
  template.parse.banned   — a banned word was found; BannedWordError is raised
  template.parse.end      — parsing complete
  template.generate.start — AST about to be compiled to Python source
  template.generate.end   — Python source generated
  template.compile.start  — Python source about to be compiled to bytecode
  template.compile.end    — bytecode ready
  template.load.start     — get_template() called (may hit the template cache)
  template.load.end       — template object returned (cached or freshly compiled)
  template.render.start   — render() called; logs context variable names
  template.render.end     — render complete; logs elapsed time and output size
  template.render.error   — render raised an exception

Usage with Flask:
    from jinja2_logging_ext import LoggingExtension, BannedWordError
    app.jinja_env.add_extension(LoggingExtension)
    app.jinja_env.banned_words = {"secret", "password"}  # raises BannedWordError on match
"""
import json
import logging
import re
import time

from jinja2.ext import Extension

logger = logging.getLogger("jinja2.lifecycle")


class BannedWordError(Exception):
    """Raised when a banned word is encountered during template parsing."""

    def __init__(self, word: str, token_type: str, name: str, lineno: int) -> None:
        self.word = word
        self.token_type = token_type
        self.template_name = name
        self.lineno = lineno
        super().__init__(
            f"Banned word {word!r} ({token_type}) in template {name!r} at line {lineno}"
        )


class LoggingExtension(Extension):
    tags: set = set()  # no custom template tags

    def __init__(self, environment):
        super().__init__(environment)
        logger.debug("[jinja2] extension.init")
        self._wrapped_template_ids: set = set()
        self._patch_environment(environment)
        environment.filters["transform"] = self._filter_transform
        environment.globals["helper"] = self._global_helper

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_transform(value: str) -> str:
        """Placeholder filter — replace with real string logic as needed.

        Usage in templates:  {{ some_var | transform }}
        """
        # TODO: replace with actual string operation
        return value

    @staticmethod
    def _global_helper(*args, **kwargs) -> str:
        """Placeholder global function — replace with real logic as needed.

        Usage in templates:  {{ helper("foo", key="bar") }}
        """
        return args[0] if len(args)> 0 else ""

    # ------------------------------------------------------------------
    # Environment patching
    # ------------------------------------------------------------------

    def _patch_environment(self, env) -> None:
        self._patch_parse(env)
        self._patch_generate(env)
        self._patch_compile(env)
        self._patch_get_template(env)

    def _patch_parse(self, env) -> None:
        _orig = env._parse

        def _parse(source, name, filename):
            label = name or filename or "<string>"
            logger.debug(
                "[jinja2] template.parse.start  name=%s chars=%d", label, len(source)
            )
            banned = getattr(env, "banned_words", set())
            prev_token_type = None
            for lineno, token_type, value in env.lex(source, name, filename):
                logger.debug(
                    "[jinja2] token  name=%s line=%-3d type=%-20s value=%r",
                    label, lineno, token_type, value,
                )
                if banned:
                    matched = next(
                        (w for w in banned if
                         (isinstance(w, re.Pattern) and w.search(value)) or
                         (isinstance(w, str) and w == value)),
                        None,
                    )
                    if matched:
                        # Allow banned words only as function arguments,
                        # i.e. when the preceding token is '(' or ','
                        if prev_token_type not in ("lparen", "comma", "operator"):
                            logger.error(
                                "[jinja2] template.parse.banned  name=%s line=%d type=%s word=%r value=%r, prev_token_type=%s",
                                label, lineno, token_type, matched, value, prev_token_type
                            )
                            raise BannedWordError(matched, token_type, label, lineno)
                prev_token_type = token_type
            result = _orig(source, name, filename)
            logger.debug("[jinja2] template.parse.end    name=%s", label)
            return result

        env._parse = _parse

    def _patch_generate(self, env) -> None:
        _orig = getattr(env, "_generate", None)
        if _orig is None:
            return

        def _generate(source, name, filename, defer_init=False):
            label = name or filename or "<string>"
            logger.debug("[jinja2] template.generate.start  name=%s", label)
            result = _orig(source, name, filename, defer_init)
            logger.debug(
                "[jinja2] template.generate.end    name=%s py_chars=%d",
                label,
                len(result) if isinstance(result, str) else -1,
            )
            return result

        env._generate = _generate

    def _patch_compile(self, env) -> None:
        _orig = getattr(env, "_compile", None)
        if _orig is None:
            return

        def _compile(source, filename):
            label = filename or "<string>"
            logger.debug("[jinja2] template.compile.start  name=%s", label)
            result = _orig(source, filename)
            logger.debug("[jinja2] template.compile.end    name=%s", label)
            return result

        env._compile = _compile

    def _patch_get_template(self, env) -> None:
        _orig = env.get_template

        def _get_template(name, *args, **kwargs):
            # defer_init is a Jinja2-internal kwarg used during environment
            # overlay/rebind; strip it before forwarding to the original method.
            kwargs.pop("defer_init", None)
            logger.debug("[jinja2] template.load.start  name=%s, args=%s, kwargs=%s", name,
                         json.dumps(args),
                         json.dumps(kwargs))
            t0 = time.perf_counter()
            tmpl = _orig(name, *args, **kwargs)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.debug(
                "[jinja2] template.load.end    name=%s elapsed_ms=%.2f", name, elapsed_ms
            )
            if id(tmpl) not in self._wrapped_template_ids:
                self._wrapped_template_ids.add(id(tmpl))
                self._patch_render(tmpl, name)
            return tmpl

        env.get_template = _get_template

    # ------------------------------------------------------------------
    # Template render patching
    # ------------------------------------------------------------------

    def _patch_render(self, tmpl, name: str) -> None:
        _orig = tmpl.render

        def _render(*args, **kwargs):
            context_keys = list(kwargs.keys())
            if args and isinstance(args[0], dict):
                context_keys = list(args[0].keys()) + context_keys
            logger.debug(
                "[jinja2] template.render.start  name=%s context_keys=%s",
                name,
                context_keys,
            )
            t0 = time.perf_counter()
            try:
                output = _orig(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.debug(
                    "[jinja2] template.render.end    name=%s elapsed_ms=%.2f bytes=%d",
                    name,
                    elapsed_ms,
                    len(output),
                )
                return output
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.error(
                    "[jinja2] template.render.error  name=%s elapsed_ms=%.2f error=%r",
                    name,
                    elapsed_ms,
                    exc,
                )
                raise

        tmpl.render = _render

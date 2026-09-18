import pytest

from jev_pilot.safety import SafetyError, SafetyPolicy, host_of


def test_host_of_handles_common_shapes():
    assert host_of("https://en.wikipedia.org/wiki/X") == "en.wikipedia.org"
    assert host_of("https://Example.TEST:8443/path") == "example.test"
    assert host_of("file:///C:/tmp/index.html") == "file"
    assert host_of("about:blank") is None
    assert host_of(None) is None


def test_policy_needs_at_least_one_host():
    with pytest.raises(SafetyError):
        SafetyPolicy.for_hosts([])


def test_for_url_derives_the_host():
    policy = SafetyPolicy.for_url("https://example.test/a")
    assert policy.host_allowed("https://example.test/b") is True
    assert policy.host_allowed("https://sub.example.test/b") is True
    assert policy.host_allowed("https://evil.test/b") is False


def test_subdomain_trick_is_refused():
    policy = SafetyPolicy.for_hosts(["example.test"])
    assert policy.host_allowed("https://notexample.test/") is False
    assert policy.host_allowed("https://example.test.evil.test/") is False


def test_check_url_refuses_a_foreign_host():
    policy = SafetyPolicy.for_hosts(["example.test"])
    with pytest.raises(SafetyError) as excinfo:
        policy.check_url("https://evil.test/login")
    assert "not in the allow list" in str(excinfo.value)


def test_check_url_refuses_when_no_hosts_declared():
    with pytest.raises(SafetyError):
        SafetyPolicy().check_url("https://example.test/")


def test_file_urls_are_allowable_explicitly():
    policy = SafetyPolicy.for_hosts(["file"])
    policy.check_url("file:///C:/tmp/index.html")
    with pytest.raises(SafetyError):
        policy.check_url("https://example.test/")


def test_only_declared_actions_are_allowed():
    policy = SafetyPolicy.for_hosts(["example.test"])
    policy.check_action("click", "https://example.test/")
    with pytest.raises(SafetyError):
        policy.check_action("type_text", "https://example.test/")


def test_typing_is_off_by_default():
    policy = SafetyPolicy.for_hosts(["example.test"])
    with pytest.raises(SafetyError):
        policy.require_typing_allowed()
    SafetyPolicy.for_hosts(["example.test"], allow_typing=True).require_typing_allowed()


def test_step_budget_is_capped():
    policy = SafetyPolicy.for_hosts(["example.test"], max_steps=5)
    assert policy.cap_steps(None) == 5
    assert policy.cap_steps(50) == 5
    assert policy.cap_steps(2) == 2
    assert policy.cap_steps(0) == 1


def test_describe_names_the_box():
    text = SafetyPolicy.for_hosts(["example.test"], dry_run=True).describe()
    assert "example.test" in text and "dry_run=True" in text


def test_a_hostless_policy_still_allows_a_click_on_a_native_window():
    """Desktop surfaces have no URL, so the host list is empty by design; the action
    allow list is what protects them."""
    policy = SafetyPolicy(allow_actions=("click",))
    policy.check_action("click")  # no url: nothing to check against
    with pytest.raises(SafetyError):
        policy.check_action("click", "https://evil.test/")  # a url appears: still refused
    with pytest.raises(SafetyError):
        policy.check_action("type_text")

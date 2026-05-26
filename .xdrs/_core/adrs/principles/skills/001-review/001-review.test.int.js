'use strict';

const path = require('path');
const { copilotCmd, testPrompt } = require('xdrs-core');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..', '..');

jest.setTimeout(300000);

test('smoke test', async () => {
	const err = await testPrompt(
		{
			workspaceRoot: REPO_ROOT,
			workspaceMode: 'in-place',
			...copilotCmd(REPO_ROOT),
		},
		'Reply ONLY with "READY" after checking if SKILL 001 has any contents',
		'Verify that the final output is ONLY "READY" and that it read file 001-review/SKILL.md',
		null,
		true
	);

	expect(err).toBe('');
});

test('001-review outputs the required review template', async () => {
	const err = await testPrompt(
		{
			workspaceRoot: REPO_ROOT,
			workspaceMode: 'copy',
			...copilotCmd(REPO_ROOT),
		},
		'Review XDRS Policy 001-xdrs-core',
		'Verify that the skill 001-review was used, contains "## Findings", and "## Summary", includes an "Outcome: PASS", and that it read file 001-review/SKILL.md and 001-xdrs-core.md.',
		null,
		true
	);

	expect(err).toBe('');
});
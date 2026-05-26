'use strict';

const path = require('path');
const { copilotCmd, testPrompt } = require('xdrs-core');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..', '..');

jest.setTimeout(300000);

test('002-write-policy creates a local EDR policy', async () => {
	const err = await testPrompt(
		{
			workspaceRoot: REPO_ROOT,
			workspaceMode: 'copy',
			...copilotCmd(REPO_ROOT),
		},
		'Create a very small XDRS Policy deciding to use pnpm for Node.js monorepos',
		'Verify that an XDRS Policy markdown file was created under .xdrs/_local/edrs/devops/, that it contains "## Context and Problem Statement" and "## Decision Outcome", that it read file 002-write-policy/SKILL.md and has the decision of using pnpm for Node.js monorepos.',
		null,
		true
	);

	expect(err).toBe('');
});
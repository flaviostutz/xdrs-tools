'use strict';

const path = require('path');
const { copilotCmd, testPrompt } = require('xdrs-core');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..', '..');

jest.setTimeout(300000);

test('004-write-article creates a local principles article', async () => {
	const err = await testPrompt(
		{
			workspaceRoot: REPO_ROOT,
			workspaceMode: 'copy',
			...copilotCmd(REPO_ROOT),
		},
		'Create a short article for new users explaining the overall principles of xdrs, element types and the role of each document in adrs',
		'Verify that an article markdown file was created under .xdrs/_local/adrs/principles/articles/ and that it has references to 001-xdrs-core.md',
		null,
		true
	);

	expect(err).toBe('');
});
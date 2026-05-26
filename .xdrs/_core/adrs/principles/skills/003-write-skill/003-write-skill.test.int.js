'use strict';

const path = require('path');
const { copilotCmd, testPrompt } = require('xdrs-core');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..', '..');

jest.setTimeout(300000);

test('003-write-skill creates a devops skill package', async () => {
	const err = await testPrompt(
		{
			workspaceRoot: REPO_ROOT,
			workspaceMode: 'copy',
			...copilotCmd(REPO_ROOT),
		},
		'Create a skill with instructions on how to do a call to a customer during a marketing campaign: - look for the phone number in the CRM opportunity, - read the proposal to be offered, - make the call, - maintain a friendly and professional tone, - report the outcome on CRM, - say "Thank you for your time".',
		'Verify that SKILL.md was created under .xdrs/_local/bdrs/marketing/skills and has instructions about calling a customer, especifically about the tone of voice',
		null,
		true
	);

	expect(err).toBe('');
});
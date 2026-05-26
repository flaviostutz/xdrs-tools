'use strict';

const path = require('path');
const { copilotCmd, testPrompt } = require('xdrs-core');

const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..', '..', '..');

jest.setTimeout(600000);

test('005-write-research creates an IMRAD research document in copy mode', async () => {
	const err = await testPrompt(
		{
			workspaceRoot: REPO_ROOT,
			workspaceMode: 'copy',
			...copilotCmd(REPO_ROOT),
		},
		'Create a very small research document in principles subject with the following data: Java vs Python for datascience projects. Java has much less libraries and community momentum than Python. Java is faster, but in general our DS applications doesn\'t require high performance. Is some cases we could use Spark for data and very specific ETL and transformations, but in general Python should be the norm for Data Science projects, especially in the early phases.',
		'Verify that a research file was created under .xdrs/_local/edrs/application/researches/, that it contains the sections Abstract, Introduction, Methods, Results, Discussion, Conclusion, and References, have the right ratio of words on the sections (not worse than 50% in deviation) and that the content contains all the provided data in input prompt, and doesn\'t contain more than 20% of additional information outside the central topic. Check also if there is at least one comparison table between the options, ',
		null,
		true
	);

	expect(err).toBe('');
});
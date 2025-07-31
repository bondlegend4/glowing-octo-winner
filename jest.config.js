// jest.config.js
export default {
    // The test environment that will be used for testing
    testEnvironment: 'node',
  
    // A list of paths to directories that Jest should use to search for files in
    roots: ['<rootDir>'],
  
    // Stop running tests after `n` failures
    bail: 1,
  
    // Indicates whether each individual test should be reported during the run
    verbose: true,
  
    // By default, jest doesn't transform node_modules.
    // We need to tell it to transform puppeteer and its dependencies.
    transformIgnorePatterns: [
      '/node_modules/(?!(puppeteer|@puppeteer/browsers)/)',
    ],
  
    // The transform section is often not needed if babel.config.js is present,
    // but explicitly setting it can prevent issues.
    transform: {
      '^.+\\.js$': 'babel-jest',
    },
  };
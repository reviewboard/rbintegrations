import {
    buildReviewBoardExtensionConfig,
} from "@beanbag/reviewboard/packaging/js/rollup-extensions.mjs"


export default buildReviewBoardExtensionConfig({
    output: {
        name: "RBIntegrationsExtension",
    },
    modulePaths: [
        "rbintegrations/static/js/",
    ],
});

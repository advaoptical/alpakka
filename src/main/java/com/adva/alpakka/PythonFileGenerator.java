package com.adva.alpakka;

import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

import lombok.NonNull;

import com.google.common.collect.HashBasedTable;
import com.google.common.collect.Table;
import com.github.jknack.handlebars.io.ClassPathTemplateLoader;

import com.github.jknack.handlebars.Handlebars;
import com.github.jknack.handlebars.helper.StringHelpers;
import one.util.streamex.EntryStream;

import org.opendaylight.yangtools.plugin.generator.api.FileGenerator;
import org.opendaylight.yangtools.plugin.generator.api.FileGeneratorException;
import org.opendaylight.yangtools.plugin.generator.api.GeneratedFile;
import org.opendaylight.yangtools.plugin.generator.api.GeneratedFilePath;
import org.opendaylight.yangtools.plugin.generator.api.GeneratedFileType;
import org.opendaylight.yangtools.plugin.generator.api.ModuleResourceResolver;

import org.opendaylight.yangtools.yang.model.api.ContainerSchemaNode;
import org.opendaylight.yangtools.yang.model.api.DataNodeContainer;
import org.opendaylight.yangtools.yang.model.api.DataSchemaNode;
import org.opendaylight.yangtools.yang.model.api.EffectiveModelContext;
import org.opendaylight.yangtools.yang.model.api.LeafSchemaNode;
import org.opendaylight.yangtools.yang.model.api.ListSchemaNode;
import org.opendaylight.yangtools.yang.model.api.Module;


public class PythonFileGenerator implements FileGenerator {

    @NonNull
    private static final Handlebars HANDLEBARS = new Handlebars().with(new ClassPathTemplateLoader("/templates"))
            .registerHelpers(StringHelpers.class)
            .prettyPrint(true);

    @NonNull
    private final Path pythonPackageDir;

    private PythonFileGenerator(@NonNull final Path pythonPackageDir) {
        this.pythonPackageDir = pythonPackageDir;
    }

    @NonNull
    public static PythonFileGenerator usingPythonPackageDir(@NonNull final Path pythonPackageDir) {
        return new PythonFileGenerator(pythonPackageDir);
    }

    @NonNull @Override
    public Table<GeneratedFileType, GeneratedFilePath, GeneratedFile> generateFiles(
            @NonNull final EffectiveModelContext yangContext,
            @NonNull final Set<Module> yangModules,
            @NonNull final ModuleResourceResolver ignoredModuleResourcePathResolver)

            throws FileGeneratorException {

        for (@NonNull final var yangModule : yangModules) {
            for (@NonNull final var dataSchemaNode : yangModule.getChildNodes()) {
                if (dataSchemaNode instanceof ContainerSchemaNode containerSchemaNode) {
                    this.generatePythonClassPackage(this.pythonPackageDir, containerSchemaNode, yangContext);
                }
            }
        }

        return HashBasedTable.create();
    }

    @NonNull
    protected <C extends DataNodeContainer & DataSchemaNode>
    void generatePythonClassPackage(
            @NonNull final Path parentPackageDir,
            @NonNull final C yangContainer,
            @NonNull final EffectiveModelContext yangContext)

            throws FileGeneratorException {

        @NonNull final var yangContainerModule = yangContainer.getQName().getModule();

        @NonNull final var yangContainerName = new YangName(yangContainer.getQName());
        @NonNull final var yangContainerPrefix = yangContext.findModule(yangContainerModule).map(Module::getName)
                .orElseThrow(() -> new RuntimeException(String.format("Missing module %s in %s", yangContainerModule,
                        yangContext)));

        @NonNull final var leafMembersContext = new HashSet<Map<String, Object>>();
        @NonNull final var containerMembersContext = new HashSet<Map<String, Object>>();
        @NonNull final var listMembersContext = new HashSet<Map<String, Object>>();

        @NonNull final var packageDir = parentPackageDir.resolve(yangContainerName.toPythonName());
        try {
            Files.createDirectories(packageDir);

        } catch (IOException ex) {
            throw new FileGeneratorException(String.format("Failed creating directory %s", packageDir.toAbsolutePath()));
        }

        @NonNull final var pythonFile = packageDir.resolve("__init__.py").toFile();

        for (@NonNull final var dataSchemaNode : yangContainer.getChildNodes()) {
            @NonNull final var memberModule = dataSchemaNode.getQName().getModule();

            @NonNull final var memberName = new YangName(dataSchemaNode.getQName());
            @NonNull final var memberPrefix = yangContext.findModule(memberModule).map(Module::getName).orElseThrow(() ->
                    new RuntimeException(String.format("Missing module %s in %s", memberModule, yangContext)));

            @NonNull final var memberContext = Map.of(
                    "yangName", memberName,
                    "yangNamespace", memberName.getNamespace(),
                    "yangModule", memberPrefix,
                    "pythonName", memberName.toPythonName());

            if (dataSchemaNode instanceof LeafSchemaNode leafMemberSchemaNode) {
                leafMembersContext.add(memberContext);

            } else if (dataSchemaNode instanceof ContainerSchemaNode containerMemberSchemaNode) {
                containerMembersContext.add(EntryStream.of(memberContext).append(
                        "className", memberName.toPythonClassName()).toMap());

                this.generatePythonClassPackage(packageDir, containerMemberSchemaNode, yangContext);

            } else if (dataSchemaNode instanceof ListSchemaNode listMemberSchemaNode) {
                listMembersContext.add(EntryStream.of(memberContext).append(
                        "className", memberName.toPythonClassName()).toMap());

                this.generatePythonClassPackage(packageDir, listMemberSchemaNode, yangContext);
            }
        }

        try (@NonNull final var pythonFileWriter = new FileWriter(pythonFile)) {

            HANDLEBARS.compile("class.py").apply(Map.of(
                    "yangName", yangContainerName,
                    "yangNamespace", yangContainerName.getNamespace(),
                    "yangModule", yangContainerPrefix,

                    "pythonName", yangContainerName.toPythonName(),
                    "className", yangContainerName.toPythonClassName(),

                    "leafMembers", leafMembersContext,
                    "containerMembers", containerMembersContext,
                    "listMembers", listMembersContext

            ), pythonFileWriter);

        } catch (final IOException e) {
            throw new FileGeneratorException(String.format("Failed creating %s from template class.py.hbs",
                    pythonFile.getAbsolutePath()), e);
        }
    }
}